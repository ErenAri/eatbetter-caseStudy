from decimal import Decimal
from uuid import UUID

import pytest

from app.application.errors import CanonicalFoodNotFoundError
from app.application.services import FoodGroundingService
from app.domain.entities import CanonicalFood, CanonicalFoodCandidate, MealItem, NutritionPer100g


class DetailAuthoritativeProvider:
    source = "FIXTURE"
    detail_calls = 0

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=1,
                source=self.source,
                source_food_id="42",
                name="Search result",
                nutrition_per_100g=NutritionPer100g(1, 1, 1, 1),
            )
        ]

    async def get_food(self, source_food_id: str):
        self.detail_calls += 1
        return CanonicalFood(
            source=self.source,
            source_food_id=source_food_id,
            name="Detail result",
            nutrition_per_100g=NutritionPer100g(200, 20, 10, 5),
        )


@pytest.mark.asyncio
async def test_selection_fetches_details_before_storing_snapshot() -> None:
    provider = DetailAuthoritativeProvider()
    service = FoodGroundingService(provider)
    item = MealItem(
        meal_id=UUID(int=1),
        position=0,
        observed_name="  Grilled Chicken Breast  ",
        confirmed_portion_g=Decimal("50"),
    )

    candidates = await service.retrieve_candidates(item)
    await service.ground_selected_candidate(item, candidates[0].rank)

    assert provider.detail_calls == 1
    assert item.canonical_food_name == "Detail result"
    assert item.nutrition_snapshot == NutritionPer100g(200, 20, 10, 5)
    assert item.nutrition_snapshot != candidates[0].nutrition_per_100g
    assert item.final_nutrition is not None
    assert item.final_nutrition.calories_kcal == Decimal("100")


@pytest.mark.asyncio
async def test_unretrieved_candidate_rank_is_rejected() -> None:
    service = FoodGroundingService(DetailAuthoritativeProvider())
    item = MealItem(meal_id=UUID(int=1), position=0, observed_name="rice")

    with pytest.raises(CanonicalFoodNotFoundError):
        await service.ground_selected_candidate(item, 1)
