from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.errors import (
    ClarificationAnswerConflictError,
    ClarificationNotFoundError,
    ValidationError,
)
from app.domain.entities import Clarification, Correction, Meal, MealItem, PortionEstimate
from app.domain.enums import ClarificationStatus, PortionResolutionSource
from app.domain.policies import UncertaintyPolicy, UncertaintyReason
from app.domain.ports import MealRepository
from app.observability.logging import log_event

from .food_grounding_service import FoodGroundingService
from .meal_canonicalization_service import MealCanonicalizationService


class MealReviewService:
    """Deterministic P6 policy orchestration. It never calls an LLM to score risk or write questions."""

    _GENERIC_HIDDEN = {"oil", "cooking oil", "cooking fat", "sauce", "dressing"}

    def __init__(
        self,
        repository: MealRepository,
        grounding: FoodGroundingService,
        canonicalization: MealCanonicalizationService,
        policy: UncertaintyPolicy,
    ) -> None:
        self.repository = repository
        self.grounding = grounding
        self.canonicalization = canonicalization
        self.policy = policy

    async def assess_meal(self, meal: Meal, *, request_id: UUID | None = None) -> Meal:
        active = [item for item in meal.items if not item.is_removed]
        for item in active:
            if item.canonical_food_id is not None:
                self._dismiss_pending(meal, f"canonical:{item.id}")
                self._dismiss_pending(meal, f"identity:{item.id}")
            if item.confirmed_portion_g is not None:
                self._dismiss_pending(meal, f"portion:{item.id}")
        unresolved = [item for item in active if item.canonical_food_id is None]
        if unresolved:
            for item in unresolved:
                self._ensure_identity(meal, item)
            self._refresh_flags(meal)
            await self.repository.save(meal)
            return meal

        hidden = [
            ingredient
            for ingredient in self._hidden_ingredients(meal)
            if not self._overlaps_active_food(active, str(ingredient["name"]))
        ]
        for ingredient in hidden:
            if ingredient["potential_impact"] in {"MATERIAL", "UNKNOWN"}:
                self._ensure_hidden(meal, ingredient)
        if self._has_blocking(meal, "HIDDEN_INGREDIENT"):
            self._refresh_flags(meal)
            await self.repository.save(meal)
            return meal

        for item in active:
            assessment = self.policy.assess_item(item)
            log_event(
                "uncertainty_assessment_completed",
                meal_id=meal.id,
                meal_item_id=item.id,
                risk_level=assessment.level,
                reason_codes=list(assessment.reasons),
                absolute_kcal_uncertainty=(
                    assessment.portion.absolute_calorie_uncertainty if assessment.portion else None
                ),
                relative_kcal_uncertainty=(
                    assessment.portion.relative_calorie_uncertainty if assessment.portion else None
                ),
            )
            if assessment.auto_accept_eligible and assessment.portion and assessment.portion.midpoint_g is not None:
                item.confirmed_portion_g = assessment.portion.midpoint_g
                item.portion_resolution_source = PortionResolutionSource.AUTO_ESTIMATE
                item.recalculate()
                self._dismiss_pending(meal, f"portion:{item.id}")
                log_event(
                    "portion_auto_resolved",
                    meal_id=meal.id,
                    meal_item_id=item.id,
                    portion_resolution_source=PortionResolutionSource.AUTO_ESTIMATE,
                )
            elif item.confirmed_portion_g is None:
                if UncertaintyReason.LOW_OBSERVATION_CERTAINTY in assessment.reasons:
                    self._ensure_identity(meal, item, reasons=assessment.reasons)
                else:
                    self._ensure_portion(meal, item, assessment.reasons)
        self._refresh_flags(meal)
        await self.repository.save(meal)
        log_event(
            "meal_uncertainty_assessed",
            meal_id=meal.id,
            blocking_clarification_count=sum(
                1 for value in meal.clarifications if value.blocking and not value.resolution_satisfied
            ),
        )
        return meal

    async def answer(
        self,
        meal: Meal,
        clarification_id: UUID,
        *,
        option_id: str | None,
        custom_grams: Decimal | None,
        request_id: UUID | None = None,
    ) -> Meal:
        clarification = next((value for value in meal.clarifications if value.id == clarification_id), None)
        if clarification is None:
            raise ClarificationNotFoundError("Clarification was not found.")
        answer, option = self._validated_answer(clarification, option_id, custom_grams)
        if clarification.status == ClarificationStatus.ANSWERED:
            if clarification.answer == answer:
                return meal
            raise ClarificationAnswerConflictError("Clarification already has a different answer.")
        if clarification.status != ClarificationStatus.PENDING:
            raise ClarificationAnswerConflictError("Clarification is no longer answerable.")

        satisfied = True
        item = self._item(meal, clarification.meal_item_id) if clarification.meal_item_id else None
        value = option.get("value", {}) if option else {}
        if clarification.type == "CANONICAL_SELECTION":
            assert item is not None
            if value.get("action") == "MANUAL_SEARCH":
                satisfied = False
            else:
                before = self._canonical_value(item)
                await self.grounding.ground_selected_candidate(item, int(value["candidate_rank"]))
                item.observation_certainty = "HIGH"
                self._record(meal, item, "canonical_food", before, self._canonical_value(item))
                if item.portion_resolution_source == PortionResolutionSource.AUTO_ESTIMATE:
                    item.confirmed_portion_g = None
                    item.portion_resolution_source = None
                    item.final_nutrition = None
        elif clarification.type == "PORTION":
            assert item is not None
            grams = custom_grams if custom_grams is not None else Decimal(str(value["grams"]))
            self._record(meal, item, "portion_g", item.confirmed_portion_g, grams)
            if grams == 0:
                self._record(meal, item, "removed_item", False, True)
                item.is_removed = True
                item.confirmed_portion_g = None
                item.portion_resolution_source = None
            else:
                item.confirmed_portion_g = grams
                item.portion_resolution_source = (
                    PortionResolutionSource.USER_HOUSEHOLD_UNIT
                    if value.get("household_unit") else PortionResolutionSource.USER
                )
            item.recalculate()
            log_event(
                "portion_user_resolved",
                meal_id=meal.id,
                meal_item_id=item.id,
                portion_resolution_source=item.portion_resolution_source,
            )
        elif clarification.type == "FOOD_IDENTITY":
            assert item is not None
            action = value.get("action")
            if action == "REMOVE_ITEM":
                item.is_removed = True
                item.recalculate()
            else:
                satisfied = False
        elif clarification.type == "HIDDEN_INGREDIENT":
            presence = value.get("presence")
            if presence == "NOT_SURE":
                satisfied = False
            elif presence == "YES":
                name = str(value["name"])
                added = MealItem(
                    meal_id=meal.id,
                    position=max((entry.position for entry in meal.items), default=-1) + 1,
                    observed_name=name,
                    normalized_name=self._normalize(name),
                    portion_estimate=PortionEstimate(),
                    observation_certainty="LOW",
                    is_user_added=True,
                )
                meal.items.append(added)
                self._record(meal, added, "added_hidden_ingredient", None, name)
                if added.normalized_name not in self._GENERIC_HIDDEN:
                    await self.canonicalization.canonicalize_item(
                        meal, added, request_id=request_id, user_context=meal.user_context
                    )
        clarification.answer_with(answer, resolution_satisfied=satisfied)
        log_event(
            "clarification_answered",
            meal_id=meal.id,
            clarification_id=clarification.id,
            clarification_type=clarification.type,
            resolution_satisfied=satisfied,
        )
        return await self.assess_meal(meal, request_id=request_id)

    def _ensure_identity(
        self,
        meal: Meal,
        item: MealItem,
        *,
        reasons: tuple[UncertaintyReason, ...] | None = None,
    ) -> None:
        key = f"canonical:{item.id}" if item.candidates else f"identity:{item.id}"
        if self._find_key(meal, key):
            return
        if item.candidates:
            options = tuple(
                [
                    {"id": f"candidate-{candidate.rank}", "label": candidate.display_name(), "value": {"candidate_rank": candidate.rank}}
                    for candidate in item.candidates
                ]
                + [
                    {
                        "id": "manual-search",
                        "label": "Search for another food",
                        "value": {"action": "MANUAL_SEARCH"},
                    }
                ]
            )
            clarification_type = "CANONICAL_SELECTION"
            question = f"Which option best describes the {item.observed_name} you ate?"
            default_reasons = (UncertaintyReason.CANONICAL_AMBIGUOUS,)
        else:
            options = (
                {"id": "manual-search", "label": "Search for another food", "value": {"action": "MANUAL_SEARCH"}},
                {"id": "remove-item", "label": "This food is not in my meal", "value": {"action": "REMOVE_ITEM"}},
            )
            clarification_type = "FOOD_IDENTITY"
            question = f"I couldn't confidently match {item.observed_name}. What was it?"
            default_reasons = (UncertaintyReason.CANONICAL_UNRESOLVED,)
        self._append(meal, key, clarification_type, question, item.id, options, reasons or default_reasons)

    def _ensure_portion(self, meal: Meal, item: MealItem, reasons: tuple[UncertaintyReason, ...]) -> None:
        key = f"portion:{item.id}"
        if self._find_key(meal, key):
            return
        values: list[tuple[str, str, Decimal]] = []
        if item.portion_estimate.min_g is not None and item.portion_estimate.max_g is not None:
            minimum = item.portion_estimate.min_g
            maximum = item.portion_estimate.max_g
            midpoint = (minimum + maximum) / Decimal("2")
            values = (
                [("estimated", f"About {midpoint.normalize()} g", midpoint)]
                if minimum == maximum
                else [
                    ("smaller", f"About {minimum.normalize()} g", minimum),
                    ("estimated", f"About {midpoint.normalize()} g", midpoint),
                    ("larger", f"About {maximum.normalize()} g", maximum),
                ]
            )
        options = tuple(
            {"id": option_id, "label": label, "value": {"grams": str(grams)}}
            for option_id, label, grams in values
        )
        self._append(
            meal,
            key,
            "PORTION",
            f"About how much {item.observed_name} did you eat?",
            item.id,
            options,
            reasons,
        )

    def _ensure_hidden(self, meal: Meal, ingredient: dict[str, Any]) -> None:
        name = str(ingredient["name"])
        normalized = self._normalize(name)
        key = f"hidden:{normalized}"
        if self._find_key(meal, key):
            return
        impact = str(ingredient["potential_impact"])
        reason = UncertaintyReason.MATERIAL_HIDDEN_INGREDIENT if impact == "MATERIAL" else UncertaintyReason.UNKNOWN_HIDDEN_INGREDIENT
        options = tuple(
            {"id": presence.lower().replace("_", "-"), "label": label, "value": {"presence": presence, "name": name}}
            for presence, label in (("NO", "No"), ("YES", "Yes"), ("NOT_SURE", "Not sure"))
        )
        self._append(
            meal,
            key,
            "HIDDEN_INGREDIENT",
            f"Was {name} used in a way the photo may not show?",
            None,
            options,
            (reason,),
        )

    @staticmethod
    def _append(meal: Meal, key: str, kind: str, question: str, item_id: UUID | None, options: tuple[dict[str, Any], ...], reasons: tuple[UncertaintyReason, ...]) -> None:
        meal.clarifications.append(Clarification(
            meal_id=meal.id,
            meal_item_id=item_id,
            type=kind,
            question=question,
            options=options,
            reason_codes=tuple(str(value) for value in reasons),
            stable_key=key,
            blocking=True,
        ))
        log_event("clarification_created", meal_id=meal.id, clarification_type=kind, stable_key=key)

    @staticmethod
    def _find_key(meal: Meal, key: str) -> Clarification | None:
        return next((value for value in meal.clarifications if value.stable_key == key), None)

    @staticmethod
    def _dismiss_pending(meal: Meal, key: str) -> None:
        clarification = MealReviewService._find_key(meal, key)
        if clarification and clarification.status == ClarificationStatus.PENDING:
            clarification.status = ClarificationStatus.DISMISSED
            clarification.resolution_satisfied = True

    @staticmethod
    def _has_blocking(meal: Meal, kind: str) -> bool:
        return any(value.type == kind and value.blocking and not value.resolution_satisfied for value in meal.clarifications)

    @staticmethod
    def _hidden_ingredients(meal: Meal) -> list[dict[str, Any]]:
        run = next((value for value in reversed(meal.ai_runs) if value.stage == "MEAL_RECOGNITION" and value.status == "SUCCEEDED" and value.structured_output), None)
        if run is None:
            return []
        found: dict[str, dict[str, Any]] = {}
        for value in run.structured_output.get("possible_hidden_ingredients", []):
            if isinstance(value, dict) and value.get("name"):
                found.setdefault(MealReviewService._normalize(str(value["name"])), value)
        return list(found.values())

    @staticmethod
    def _overlaps_active_food(items: list[MealItem], hidden_name: str) -> bool:
        ignored = {"additional", "added", "extra", "hidden", "possible", "cooking"}
        hidden_tokens = set(re.findall(r"[a-z0-9]+", hidden_name.lower())) - ignored
        if not hidden_tokens:
            return False
        for item in items:
            visible = " ".join(
                value
                for value in (item.observed_name, item.normalized_name, item.canonical_food_name)
                if value
            )
            visible_tokens = set(re.findall(r"[a-z0-9]+", visible.lower()))
            if hidden_tokens <= visible_tokens:
                return True
        return False

    @staticmethod
    def _validated_answer(clarification: Clarification, option_id: str | None, custom_grams: Decimal | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if custom_grams is not None:
            if clarification.type != "PORTION" or custom_grams < 0:
                raise ValidationError("Custom grams are only valid for portion clarifications.")
            return {"custom_grams": custom_grams}, None
        option = next((value for value in clarification.options if value.get("id") == option_id), None)
        if option is None:
            raise ValidationError("option_id is not valid for this clarification")
        return {"option_id": option_id}, option

    @staticmethod
    def _refresh_flags(meal: Meal) -> None:
        for item in meal.items:
            blocking = any(value.meal_item_id == item.id and value.blocking and not value.resolution_satisfied for value in meal.clarifications)
            item.requires_clarification = blocking and not item.is_removed
            item.clarification_resolved = not blocking

    @staticmethod
    def _item(meal: Meal, item_id: UUID | None) -> MealItem:
        item = next((value for value in meal.items if value.id == item_id), None)
        if item is None:
            raise ValidationError("Clarification references a missing meal item.")
        return item

    @staticmethod
    def _record(meal: Meal, item: MealItem, field_name: str, predicted: Any, corrected: Any) -> None:
        meal.corrections.append(Correction(meal_id=meal.id, meal_item_id=item.id, field_name=field_name, predicted_value=predicted, corrected_value=corrected))

    @staticmethod
    def _canonical_value(item: MealItem) -> dict[str, Any] | None:
        return None if item.canonical_food_id is None else {"source": item.canonical_source, "food_id": item.canonical_food_id, "name": item.canonical_food_name, "candidate_rank": item.canonical_candidate_rank}

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())