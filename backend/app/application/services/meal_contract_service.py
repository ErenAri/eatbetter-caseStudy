from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.errors import (
    CanonicalFoodNotFoundError,
    ImageTooLargeError,
    InvalidMealStateError,
    ItemNotFoundError,
    MealNotFoundError,
    UnresolvedClarificationsError,
    UnsupportedImageError,
    ValidationError,
)
from app.domain.entities import Correction, Meal, MealItem, NutritionTotals
from app.domain.enums import ClarificationStatus, MealStatus, PortionResolutionSource
from app.domain.ports import MealRepository, StorageProvider
from app.domain.policies import UncertaintyPolicy
from app.observability.logging import log_event

from .food_grounding_service import FoodGroundingService
from .meal_canonicalization_service import MealCanonicalizationService
from .meal_recognition_service import MealRecognitionService
from .meal_review_service import MealReviewService


class MealContractService:
    def __init__(
        self,
        repository: MealRepository,
        storage: StorageProvider,
        grounding: FoodGroundingService,
        recognition: MealRecognitionService,
        canonicalization: MealCanonicalizationService,
        review: MealReviewService | None = None,
        *,
        max_upload_bytes: int,
        allowed_mime_types: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.grounding = grounding
        self.recognition = recognition
        self.canonicalization = canonicalization
        self.review = review or MealReviewService(
            repository, grounding, canonicalization, UncertaintyPolicy()
        )
        self.max_upload_bytes = max_upload_bytes
        self.allowed_mime_types = allowed_mime_types

    async def create_meal(
        self,
        *,
        user_id: UUID,
        meal_request_id: UUID,
        logged_at: datetime,
        user_context: str | None,
    ) -> tuple[Meal, bool]:
        if logged_at.tzinfo is None:
            raise ValidationError("logged_at must include a timezone offset")
        meal = Meal(
            user_id=user_id,
            meal_request_id=meal_request_id,
            logged_at=logged_at.astimezone(timezone.utc),
            user_context=user_context,
        )
        return await self.repository.create(meal)

    async def get_meal(self, meal_id: UUID, user_id: UUID) -> Meal:
        meal = await self.repository.get_owned(meal_id, user_id)
        if meal is None:
            raise MealNotFoundError("Meal was not found.")
        return meal

    async def attach_image(
        self,
        *,
        meal_id: UUID,
        user_id: UUID,
        content: bytes,
        mime_type: str,
    ) -> Meal:
        meal = await self.get_meal(meal_id, user_id)
        if meal.status != MealStatus.UPLOADED:
            raise InvalidMealStateError("Images can only be attached before analysis starts.")
        if mime_type not in self.allowed_mime_types or not self._matches_signature(content, mime_type):
            raise UnsupportedImageError("The uploaded file is not a supported image.")
        if len(content) > self.max_upload_bytes:
            raise ImageTooLargeError("The uploaded image exceeds the configured size limit.")
        if not content:
            raise UnsupportedImageError("The uploaded image is empty.")
        new_path = await self.storage.put_private(content, mime_type)
        previous_path = meal.image_path
        meal.image_path = new_path
        meal.updated_at = datetime.now(timezone.utc)
        await self.repository.save(meal)
        if previous_path:
            await self.storage.delete(previous_path)
        return meal

    async def start_analysis(
        self, meal_id: UUID, user_id: UUID, request_id: UUID | None = None
    ) -> Meal:
        meal = await self.recognition.analyze(
            meal_id=meal_id, user_id=user_id, request_id=request_id
        )
        meal = await self.canonicalization.canonicalize_meal(
            meal, request_id=request_id
        )
        return await self.review.assess_meal(meal, request_id=request_id)

    async def list_meals(
        self,
        *,
        user_id: UUID,
        on_date: date | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Meal], str | None]:
        return await self.repository.list_owned(
            user_id, on_date=on_date, limit=limit, cursor=cursor
        )

    async def update_item(
        self,
        *,
        meal_id: UUID,
        item_id: UUID,
        user_id: UUID,
        changes: dict[str, Any],
    ) -> Meal:
        meal = await self._reviewable_meal(meal_id, user_id)
        item = self._item(meal, item_id)
        allowed = {"candidate_rank", "portion_g", "preparation_method"}
        if not changes or not set(changes).issubset(allowed):
            raise ValidationError("No supported item correction was supplied.")

        if "candidate_rank" in changes:
            rank = changes["candidate_rank"]
            before = self._canonical_value(item)
            await self.grounding.ground_selected_candidate(item, rank)
            if item.portion_resolution_source == PortionResolutionSource.AUTO_ESTIMATE:
                item.confirmed_portion_g = None
                item.portion_resolution_source = None
                item.final_nutrition = None
            self._record(meal, item, "canonical_food", before, self._canonical_value(item))

        if "portion_g" in changes:
            grams = Decimal(str(changes["portion_g"]))
            if grams <= 0:
                raise ValidationError("portion_g must be positive")
            predicted: Any = item.confirmed_portion_g
            if predicted is None:
                predicted = {
                    "min_g": item.portion_estimate.min_g,
                    "max_g": item.portion_estimate.max_g,
                }
            self._record(meal, item, "portion_g", predicted, grams)
            item.confirmed_portion_g = grams
            item.portion_resolution_source = PortionResolutionSource.USER

        if "preparation_method" in changes:
            preparation = changes["preparation_method"]
            self._record(
                meal,
                item,
                "preparation_method",
                item.preparation_method,
                preparation,
            )
            item.preparation_method = preparation

        item.recalculate()
        await self.repository.save(meal)
        return await self.review.assess_meal(meal)

    async def remove_item(self, *, meal_id: UUID, item_id: UUID, user_id: UUID) -> Meal:
        meal = await self._reviewable_meal(meal_id, user_id)
        item = self._item(meal, item_id)
        if not item.is_removed:
            self._record(meal, item, "removed_item", False, True)
            item.is_removed = True
            item.clarification_resolved = True
            item.recalculate()
            for clarification in meal.clarifications:
                if (
                    clarification.meal_item_id == item.id
                    and clarification.status == ClarificationStatus.PENDING
                ):
                    clarification.status = ClarificationStatus.DISMISSED
                    clarification.resolution_satisfied = True
        await self.repository.save(meal)
        return await self.review.assess_meal(meal)

    async def replace_item(
        self,
        *,
        meal_id: UUID,
        item_id: UUID,
        user_id: UUID,
        query: str,
        portion_g: Decimal,
        request_id: UUID | None = None,
    ) -> Meal:
        meal = await self._reviewable_meal(meal_id, user_id)
        item = self._item(meal, item_id)
        if portion_g <= 0:
            raise ValidationError("portion_g must be positive")
        normalized = query.strip().lower()
        if not normalized:
            raise ValidationError("query cannot be blank")
        before = {
            "observed_name": item.observed_name,
            "canonical_food": self._canonical_value(item),
            "portion_g": item.confirmed_portion_g,
        }
        for clarification in meal.clarifications:
            if (
                clarification.meal_item_id == item.id
                and clarification.status == ClarificationStatus.PENDING
            ):
                clarification.status = ClarificationStatus.DISMISSED
                clarification.resolution_satisfied = True
                clarification.stable_key = (
                    f"{clarification.stable_key}:superseded:{clarification.id}"
                )
        item.observed_name = query.strip()
        item.normalized_name = normalized
        item.canonical_food_id = None
        item.canonical_food_name = None
        item.canonical_source = None
        item.canonical_candidate_rank = None
        item.canonical_confidence = None
        item.nutrition_snapshot = None
        item.nutrition_retrieved_at = None
        item.final_nutrition = None
        item.candidates = []
        item.confirmed_portion_g = Decimal(str(portion_g))
        item.portion_resolution_source = PortionResolutionSource.USER
        item.observation_certainty = "HIGH"
        item.requires_clarification = True
        item.clarification_resolved = False
        item.is_user_added = True
        self._record(
            meal,
            item,
            "food_replacement",
            before,
            {"query": item.observed_name, "portion_g": item.confirmed_portion_g},
        )
        await self.canonicalization.canonicalize_item(
            meal,
            item,
            request_id=request_id,
            user_context=meal.user_context,
            force=True,
        )
        await self.repository.save(meal)
        return await self.review.assess_meal(meal, request_id=request_id)

    async def add_missing_item(
        self,
        *,
        meal_id: UUID,
        user_id: UUID,
        query: str,
        portion_g: Decimal,
        request_id: UUID | None = None,
    ) -> Meal:
        meal = await self._reviewable_meal(meal_id, user_id)
        if portion_g <= 0:
            raise ValidationError("portion_g must be positive")
        item = MealItem(
            meal_id=meal.id,
            position=max((value.position for value in meal.items), default=-1) + 1,
            observed_name=query,
            normalized_name=query.strip().lower(),
            confirmed_portion_g=portion_g,
            portion_resolution_source=PortionResolutionSource.USER,
            requires_clarification=True,
            is_user_added=True,
        )
        meal.items.append(item)
        self._record(
            meal,
            item,
            "added_item",
            None,
            {"query": query, "portion_g": portion_g},
        )
        await self.canonicalization.canonicalize_item(
            meal,
            item,
            request_id=request_id,
            user_context=meal.user_context,
        )
        await self.repository.save(meal)
        return await self.review.assess_meal(meal, request_id=request_id)

    async def answer_clarification(
        self,
        *,
        meal_id: UUID,
        clarification_id: UUID,
        user_id: UUID,
        option_id: str | None,
        custom_grams: Decimal | None,
    ) -> Meal:
        meal = await self._reviewable_meal(meal_id, user_id)
        return await self.review.answer(
            meal,
            clarification_id,
            option_id=option_id,
            custom_grams=custom_grams,
        )

    async def confirm_meal(self, meal_id: UUID, user_id: UUID) -> Meal:
        meal = await self.get_meal(meal_id, user_id)
        if meal.status != MealStatus.NEEDS_REVIEW:
            raise InvalidMealStateError("Meal is not ready for confirmation.")
        if meal.has_unresolved_clarifications():
            raise UnresolvedClarificationsError(
                "Resolve all required clarifications before confirming the meal."
            )
        for item in meal.items:
            if item.is_removed:
                continue
            if item.canonical_food_id is None or item.nutrition_snapshot is None:
                raise CanonicalFoodNotFoundError(
                    "Every active item needs a grounded canonical food before confirmation."
                )
            if item.confirmed_portion_g is None:
                raise UnresolvedClarificationsError(
                    "Every active item needs a confirmed portion before confirmation."
                )
            if item.portion_resolution_source is None:
                raise UnresolvedClarificationsError(
                    "Every active item needs portion resolution provenance before confirmation."
                )
            item.recalculate()
            if item.final_nutrition is None:
                raise UnresolvedClarificationsError(
                    "Every active item needs final nutrition before confirmation."
                )
        meal.transition_to(MealStatus.CONFIRMED)
        await self.repository.save(meal)
        log_event("meal_ready_for_confirmation", meal_id=meal.id, active_item_count=sum(not item.is_removed for item in meal.items))
        return meal

    async def today_summary(
        self, *, user_id: UUID, on_date: date, timezone_name: str
    ) -> tuple[list[Meal], NutritionTotals]:
        try:
            user_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValidationError("timezone must be a valid IANA timezone name") from error
        meals, _ = await self.repository.list_owned(
            user_id, on_date=None, limit=1000, cursor=None
        )
        confirmed = [
            meal
            for meal in meals
            if meal.status == MealStatus.CONFIRMED
            and meal.logged_at.astimezone(user_timezone).date() == on_date
        ]
        total = NutritionTotals()
        for meal in confirmed:
            total = total + meal.totals()
        return confirmed, total

    async def delete_meal(self, meal_id: UUID, user_id: UUID) -> None:
        meal = await self.get_meal(meal_id, user_id)
        if meal.image_path:
            await self.storage.delete(meal.image_path)
        deleted = await self.repository.delete_owned(meal_id, user_id)
        if deleted is None:
            raise MealNotFoundError("Meal was not found.")

    async def _reviewable_meal(self, meal_id: UUID, user_id: UUID) -> Meal:
        meal = await self.get_meal(meal_id, user_id)
        if meal.status != MealStatus.NEEDS_REVIEW:
            raise InvalidMealStateError("Items can only be edited while a meal needs review.")
        return meal

    @staticmethod
    def _item(meal: Meal, item_id: UUID) -> MealItem:
        item = next((value for value in meal.items if value.id == item_id), None)
        if item is None:
            raise ItemNotFoundError("Meal item was not found.")
        return item

    @staticmethod
    def _record(
        meal: Meal, item: MealItem, field_name: str, predicted: Any, corrected: Any
    ) -> None:
        meal.corrections.append(
            Correction(
                meal_id=meal.id,
                meal_item_id=item.id,
                field_name=field_name,
                predicted_value=predicted,
                corrected_value=corrected,
            )
        )

    @staticmethod
    def _canonical_value(item: MealItem) -> dict[str, Any] | None:
        if item.canonical_food_id is None:
            return None
        return {
            "source": item.canonical_source,
            "food_id": item.canonical_food_id,
            "name": item.canonical_food_name,
            "candidate_rank": item.canonical_candidate_rank,
        }

    @staticmethod
    def _matches_signature(content: bytes, mime_type: str) -> bool:
        if mime_type == "image/jpeg":
            return content.startswith(b"\xff\xd8\xff")
        if mime_type == "image/png":
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        if mime_type == "image/webp":
            return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        return False
