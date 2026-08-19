from __future__ import annotations

from time import perf_counter
from uuid import UUID

from app.ai.canonicalization_errors import CanonicalizationInvalidSelectionError
from app.ai.schemas import (
    CanonicalizationCandidate,
    CanonicalizationDecision,
    CanonicalizationOutput,
    CanonicalizationReason,
    CanonicalizationRequest,
    MatchQuality,
)
from app.domain.entities import AIRun, Meal, MealItem
from app.domain.ports import CanonicalizationProvider, MealRepository
from app.nutrition.normalization import canonical_gate_token_roles
from app.observability.logging import log_event

from .food_grounding_service import FoodGroundingService


class MealCanonicalizationService:
    def __init__(
        self,
        repository: MealRepository,
        grounding: FoodGroundingService,
        provider: CanonicalizationProvider,
    ) -> None:
        self.repository = repository
        self.grounding = grounding
        self.provider = provider

    async def canonicalize_meal(
        self, meal: Meal, *, request_id: UUID | None
    ) -> Meal:
        for item in meal.items:
            if not item.is_removed:
                await self.canonicalize_item(
                    meal, item, request_id=request_id, user_context=meal.user_context
                )
        await self.repository.save(meal)
        return meal

    async def canonicalize_item(
        self,
        meal: Meal,
        item: MealItem,
        *,
        request_id: UUID | None,
        user_context: str | None,
        force: bool = False,
    ) -> None:
        if item.is_removed or (
            item.canonical_food_id is not None and item.nutrition_snapshot is not None
        ):
            return
        if not force and self._has_successful_attempt(meal, item.id):
            return

        run = AIRun(
            meal_id=meal.id,
            stage="CANONICALIZATION",
            provider=self.provider.provider_name,
            model=self.provider.model,
            prompt_version=self.provider.prompt_version,
            request_id=request_id,
            reasoning_effort=self.provider.reasoning_effort,
        )
        meal.ai_runs.append(run)
        await self.repository.save(meal)
        started = perf_counter()
        output: CanonicalizationOutput | None = None
        try:
            candidates = item.candidates or await self.grounding.retrieve_candidates(item)
            log_event(
                "canonicalization_started",
                meal_id=meal.id,
                meal_item_id=item.id,
                request_id=request_id,
                provider=run.provider,
                model=run.model,
                prompt_version=run.prompt_version,
                reasoning_effort=run.reasoning_effort,
                candidate_count=len(candidates),
            )
            if not candidates:
                run.provider = "DETERMINISTIC"
                run.model = "zero-candidate-abstain"
                run.prompt_version = "not_run"
                run.reasoning_effort = None
                output = CanonicalizationOutput(
                    decision=CanonicalizationDecision.ABSTAIN,
                    selected_candidate_rank=None,
                    match_quality=MatchQuality.NO_MATCH,
                    reason_codes=[CanonicalizationReason.NO_SUITABLE_CANDIDATE],
                )
                result = None
            else:
                request = CanonicalizationRequest(
                    meal_item_id=item.id,
                    observed_name=item.observed_name,
                    preparation_method=item.preparation_method,
                    user_context=user_context,
                    candidates=[self._candidate_input(value) for value in candidates[:5]],
                )
                result = await self.provider.select_candidate(
                    request=request, request_id=request_id
                )
                output = result.output
                try:
                    output.validate_against_supplied_ranks(
                        {candidate.rank for candidate in request.candidates}
                    )
                except ValueError:
                    raise CanonicalizationInvalidSelectionError(
                        "Canonicalization selected a rank that was not supplied."
                    ) from None
                run.provider = result.provider
                run.model = result.model
                run.prompt_version = result.prompt_version
                run.reasoning_effort = result.reasoning_effort

                if (
                    output.decision == CanonicalizationDecision.SELECT
                    and not self._selection_passes_deterministic_gate(item, candidates, output)
                ):
                    log_event(
                        "canonicalization_selection_blocked",
                        meal_id=meal.id,
                        meal_item_id=item.id,
                        request_id=request_id,
                        selected_candidate_rank=output.selected_candidate_rank,
                        model_match_quality=output.match_quality,
                        reason="deterministic_identity_or_preparation_gate",
                    )
                    output = CanonicalizationOutput(
                        decision=CanonicalizationDecision.ABSTAIN,
                        selected_candidate_rank=None,
                        match_quality=MatchQuality.AMBIGUOUS,
                        reason_codes=[CanonicalizationReason.INSUFFICIENT_OBSERVATION],
                    )

            run.structured_output = self._audit_output(item.id, output)
            if output.decision == CanonicalizationDecision.SELECT:
                await self.grounding.ground_selected_candidate(
                    item, output.selected_candidate_rank
                )
            latency_ms = round((perf_counter() - started) * 1000)
            run.succeed(
                latency_ms=latency_ms,
                input_tokens=result.input_tokens if result else None,
                output_tokens=result.output_tokens if result else None,
                structured_output=run.structured_output,
                retry_count=result.retry_count if result else 0,
            )
            event = (
                "canonicalization_completed"
                if output.decision == CanonicalizationDecision.SELECT
                else "canonicalization_abstained"
            )
            log_event(
                event,
                meal_id=meal.id,
                meal_item_id=item.id,
                request_id=request_id,
                provider=run.provider,
                model=run.model,
                prompt_version=run.prompt_version,
                reasoning_effort=run.reasoning_effort,
                candidate_count=len(candidates),
                decision=output.decision,
                match_quality=output.match_quality,
                latency_ms=latency_ms,
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                retry_count=run.retry_count,
            )
        except Exception as error:
            latency_ms = round((perf_counter() - started) * 1000)
            code = getattr(error, "code", "CANONICALIZATION_INVALID_RESPONSE")
            details = getattr(error, "details", None)
            retry_count = details.get("retry_count", 0) if isinstance(details, dict) else 0
            if output is not None:
                run.structured_output = self._audit_output(item.id, output)
            run.fail(latency_ms=latency_ms, error_code=code, retry_count=retry_count)
            log_event(
                "canonicalization_failed",
                meal_id=meal.id,
                meal_item_id=item.id,
                request_id=request_id,
                provider=run.provider,
                model=run.model,
                prompt_version=run.prompt_version,
                reasoning_effort=run.reasoning_effort,
                candidate_count=len(item.candidates),
                latency_ms=latency_ms,
                error_code=code,
                retry_count=retry_count,
            )
        await self.repository.save(meal)

    @staticmethod
    def _candidate_input(candidate) -> CanonicalizationCandidate:
        data = candidate.data if isinstance(candidate.data, dict) else {}

        def optional_text(key: str) -> str | None:
            value = data.get(key)
            return str(value) if value is not None else None

        return CanonicalizationCandidate(
            rank=candidate.rank,
            name=candidate.name,
            data_type=optional_text("data_type"),
            brand_owner=optional_text("brand_owner"),
            household_serving_full_text=optional_text(
                "household_serving_full_text"
            ),
        )

    @staticmethod
    def _selection_passes_deterministic_gate(
        item: MealItem, candidates: list, output: CanonicalizationOutput
    ) -> bool:
        selected = next(
            (candidate for candidate in candidates if candidate.rank == output.selected_candidate_rank),
            None,
        )
        if selected is None:
            return False

        identity_tokens, observed_preparation = canonical_gate_token_roles(
            item.normalized_name or item.observed_name
        )
        _, explicit_preparation = canonical_gate_token_roles(item.preparation_method or "")
        requested_preparation = observed_preparation | explicit_preparation
        selected_identity, selected_preparation = canonical_gate_token_roles(selected.name)
        if not identity_tokens or not selected_identity:
            return False

        identity_overlap = len(identity_tokens & selected_identity) / max(
            len(identity_tokens), 1
        )
        if requested_preparation and not requested_preparation.issubset(
            selected_preparation
        ):
            return False

        support_scores: list[float] = []
        for candidate in candidates[:5]:
            candidate_identity, _ = canonical_gate_token_roles(candidate.name)
            support_scores.append(
                len(identity_tokens & candidate_identity) / max(len(identity_tokens), 1)
            )
        best_support = max(support_scores, default=0.0)

        # Keep the existing calibrated safety thresholds unchanged. This PR only
        # fixes the representation supplied to the gate.
        minimum_overlap = 0.75 if output.match_quality == MatchQuality.EXACT else 0.50
        return identity_overlap >= minimum_overlap and identity_overlap >= best_support - 0.15

    @staticmethod
    def _audit_output(item_id: UUID, output: CanonicalizationOutput) -> dict:
        return {
            "meal_item_id": str(item_id),
            **output.model_dump(mode="json"),
        }

    @staticmethod
    def _has_successful_attempt(meal: Meal, item_id: UUID) -> bool:
        return any(
            run.stage == "CANONICALIZATION"
            and run.status == "SUCCEEDED"
            and run.structured_output is not None
            and run.structured_output.get("meal_item_id") == str(item_id)
            for run in meal.ai_runs
        )
