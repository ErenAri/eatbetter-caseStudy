from uuid import uuid4

import pytest

from app.nutrition.providers.demo import DemoNutritionProvider


@pytest.mark.asyncio
async def test_search_candidate_data_carries_provenance_note_not_data_type() -> None:
    """Regression guard, same bug class as the AI provider fix: the
    "TEST/DEMO DATA — NOT USDA RESULTS" label is written for humans
    (CanonicalFoodCandidate.display_name()). It must not travel under the
    `data_type` key, because meal_canonicalization_service forwards
    `data_type` to the constrained OpenAI selector -- being told a candidate
    is "NOT USDA RESULTS" would make the selector abstain. This normally
    stays latent because demo mode pairs with the deterministic
    canonicalization provider, but the field itself must still be correct.
    """
    provider = DemoNutritionProvider()

    candidates = await provider.search_foods("chicken breast", meal_item_id=uuid4())

    assert candidates, "expected the demo fixture to match 'chicken breast'"
    assert "data_type" not in candidates[0].data
    assert candidates[0].data["provenance_note"] == "TEST/DEMO DATA — NOT USDA RESULTS"


@pytest.mark.asyncio
async def test_search_candidate_display_name_is_unchanged() -> None:
    provider = DemoNutritionProvider()

    candidates = await provider.search_foods("chicken breast", meal_item_id=uuid4())

    assert (
        candidates[0].display_name()
        == "Chicken breast, grilled · TEST/DEMO DATA — NOT USDA RESULTS"
    )


@pytest.mark.asyncio
async def test_get_food_data_carries_provenance_note_not_data_type() -> None:
    provider = DemoNutritionProvider()

    food = await provider.get_food("fixture-chicken")

    assert food is not None
    assert "data_type" not in food.data
    assert food.data["provenance_note"] == "TEST/DEMO DATA — NOT USDA RESULTS"
