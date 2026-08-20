from dataclasses import replace

from app.application.errors import CanonicalFoodNotFoundError
from app.domain.entities import CanonicalFood, CanonicalFoodCandidate, MealItem
from app.domain.ports import NutritionProvider
from app.nutrition.normalization import build_grounding_query


class FoodGroundingService:
    def __init__(self, provider: NutritionProvider) -> None:
        self.provider = provider

    async def retrieve_candidates(
        self, meal_item: MealItem, *, limit: int = 5
    ) -> list[CanonicalFoodCandidate]:
        query = build_grounding_query(
            meal_item.normalized_name or meal_item.observed_name,
            meal_item.preparation_method,
        )
        retrieved = await self.provider.search_foods(
            query, meal_item_id=meal_item.id, limit=max(limit * 3, limit)
        )
        candidates: list[CanonicalFoodCandidate] = []
        seen: set[tuple[str, str, str, str]] = set()
        for candidate in retrieved:
            data = candidate.data if isinstance(candidate.data, dict) else {}
            signature = (
                " ".join(candidate.name.lower().split()),
                str(data.get("data_type", "")).lower(),
                str(data.get("brand_owner", "")).lower(),
                str(data.get("household_serving_full_text", "")).lower(),
            )
            if signature in seen:
                continue
            seen.add(signature)
            candidates.append(replace(candidate, rank=len(candidates) + 1))
            if len(candidates) == limit:
                break
        expected_ranks = list(range(1, len(candidates) + 1))
        if [candidate.rank for candidate in candidates] != expected_ranks:
            raise ValueError("nutrition provider returned non-contiguous candidate ranks")
        if any(candidate.meal_item_id != meal_item.id for candidate in candidates):
            raise ValueError("nutrition provider returned candidates for a different meal item")
        meal_item.candidates = list(candidates)
        return meal_item.candidates

    async def ground_selected_candidate(
        self, meal_item: MealItem, candidate_rank: int
    ) -> CanonicalFood:
        candidate = next(
            (value for value in meal_item.candidates if value.rank == candidate_rank), None
        )
        if candidate is None:
            raise CanonicalFoodNotFoundError(
                "The selected canonical candidate was not retrieved for this item."
            )
        data = candidate.data if isinstance(candidate.data, dict) else {}
        if (
            candidate.source == "TEST_DEMO_DATA"
            and data.get("fixture") is True
            and candidate.nutrition_per_100g is not None
        ):
            canonical = CanonicalFood(
                source=candidate.source,
                source_food_id=candidate.source_food_id,
                name=candidate.name,
                nutrition_per_100g=candidate.nutrition_per_100g,
                data=data,
                retrieved_at=candidate.created_at,
            )
        else:
            canonical = await self.provider.get_food(candidate.source_food_id)
        if canonical is None:
            raise CanonicalFoodNotFoundError("The canonical food no longer exists at its source.")
        if (
            canonical.source != candidate.source
            or canonical.source_food_id != candidate.source_food_id
        ):
            raise CanonicalFoodNotFoundError(
                "Canonical food details did not match the selected candidate."
            )
        meal_item.select_candidate(candidate_rank)
        meal_item.canonical_source = canonical.source
        meal_item.canonical_food_id = canonical.source_food_id
        meal_item.canonical_food_name = canonical.name
        meal_item.nutrition_snapshot = canonical.nutrition_per_100g
        meal_item.nutrition_retrieved_at = canonical.retrieved_at
        meal_item.nutrition_familiarity = (canonical.data or {}).get("familiarity")
        meal_item.recalculate()
        return canonical
