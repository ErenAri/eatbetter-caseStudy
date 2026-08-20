from decimal import Decimal
from uuid import UUID

import pytest

from app.application.errors import CanonicalFoodNotFoundError
from app.application.services import FoodGroundingService
from app.domain.entities import CanonicalFood, CanonicalFoodCandidate, MealItem, NutritionPer100g
from app.nutrition.normalization import build_grounding_query


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


class DuplicateProvider:
    source = "USDA"

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=rank,
                source=self.source,
                source_food_id=str(100 + rank),
                name="SPAGHETTI",
                data={"data_type": "Survey (FNDDS)"},
            )
            for rank in range(1, 4)
        ]

    async def get_food(self, source_food_id: str):
        raise AssertionError("not used")


class ExplodingDetailProvider:
    source = "USDA"

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        return []

    async def get_food(self, source_food_id: str):
        raise AssertionError("fixture selection must not call the configured provider")


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


@pytest.mark.asyncio
async def test_retrieval_deduplicates_indistinguishable_candidate_rows() -> None:
    service = FoodGroundingService(DuplicateProvider())
    item = MealItem(meal_id=UUID(int=1), position=0, observed_name="spaghetti")

    candidates = await service.retrieve_candidates(item)

    assert len(candidates) == 1
    assert candidates[0].rank == 1
    assert candidates[0].display_name() == "SPAGHETTI · FoodData Central · FNDDS"


@pytest.mark.asyncio
async def test_embedded_demo_candidate_is_provider_independent() -> None:
    service = FoodGroundingService(ExplodingDetailProvider())
    item = MealItem(
        meal_id=UUID(int=1),
        position=0,
        observed_name="cream sauce",
        confirmed_portion_g=Decimal("50"),
    )
    item.candidates = [CanonicalFoodCandidate(
        meal_item_id=item.id,
        rank=1,
        source="TEST_DEMO_DATA",
        source_food_id="fixture-cream-sauce",
        name="Cream sauce",
        data={"fixture": True},
        nutrition_per_100g=NutritionPer100g(190, 3, 8, 16),
    )]

    await service.ground_selected_candidate(item, 1)

    assert item.canonical_food_name == "Cream sauce"
    assert item.final_nutrition is not None
    assert item.final_nutrition.calories_kcal == Decimal("95")


class FamiliarityReportingProvider:
    source = "AI_ESTIMATE"

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        return [
            CanonicalFoodCandidate(
                meal_item_id=meal_item_id,
                rank=1,
                source=self.source,
                source_food_id="ai-food",
                name="AI food",
                data={"familiarity": "LOW"},
                nutrition_per_100g=NutritionPer100g(200, 20, 10, 5),
            )
        ]

    async def get_food(self, source_food_id: str):
        return CanonicalFood(
            source=self.source,
            source_food_id=source_food_id,
            name="AI food",
            nutrition_per_100g=NutritionPer100g(200, 20, 10, 5),
            data={"familiarity": "LOW"},
        )


@pytest.mark.asyncio
async def test_grounding_sets_nutrition_familiarity_from_canonical_data() -> None:
    service = FoodGroundingService(FamiliarityReportingProvider())
    item = MealItem(meal_id=UUID(int=1), position=0, observed_name="mystery dish")

    candidates = await service.retrieve_candidates(item)
    await service.ground_selected_candidate(item, candidates[0].rank)

    assert item.nutrition_familiarity == "LOW"


class QueryRecordingProvider:
    """Records the exact query string passed to search_foods."""

    source = "FIXTURE"

    def __init__(self) -> None:
        self.received_query: str | None = None

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        self.received_query = query
        return []

    async def get_food(self, source_food_id: str):
        raise AssertionError("not used")


class LexicalSearchProvider(QueryRecordingProvider):
    uses_lexical_search = True


class NonLexicalSearchProvider(QueryRecordingProvider):
    uses_lexical_search = False


@pytest.mark.asyncio
async def test_lexical_search_provider_receives_the_rewritten_query() -> None:
    provider = LexicalSearchProvider()
    service = FoodGroundingService(provider)
    item = MealItem(meal_id=UUID(int=1), position=0, observed_name="tomato sauce")

    await service.retrieve_candidates(item)

    assert provider.received_query == build_grounding_query("tomato sauce", None)
    assert provider.received_query == "tomato products canned sauce"


@pytest.mark.asyncio
async def test_provider_without_the_attribute_defaults_to_todays_rewritten_query_behavior() -> None:
    """A provider that predates `uses_lexical_search` (or simply omits it) must
    keep receiving the rewritten query -- the attribute is read defensively.
    """
    provider = QueryRecordingProvider()
    service = FoodGroundingService(provider)
    item = MealItem(meal_id=UUID(int=1), position=0, observed_name="tomato sauce")

    await service.retrieve_candidates(item)

    assert provider.received_query == "tomato products canned sauce"


@pytest.mark.asyncio
async def test_non_lexical_search_provider_receives_the_readable_observed_name() -> None:
    """The AI path must not receive USDA search-index rewrites: the model
    should be asked about a real food, and the observed name is what becomes
    the user-visible canonical_food_name.
    """
    provider = NonLexicalSearchProvider()
    service = FoodGroundingService(provider)
    item = MealItem(meal_id=UUID(int=1), position=0, observed_name="Tomato Wedges")

    await service.retrieve_candidates(item)

    assert provider.received_query == "Tomato Wedges"


@pytest.mark.asyncio
async def test_non_lexical_search_provider_falls_back_to_normalized_name_when_observed_name_is_empty() -> None:
    provider = NonLexicalSearchProvider()
    service = FoodGroundingService(provider)
    item = MealItem(
        meal_id=UUID(int=1),
        position=0,
        observed_name="",
        normalized_name="Tomato Sauce",
    )

    await service.retrieve_candidates(item)

    assert provider.received_query == "Tomato Sauce"


@pytest.mark.asyncio
async def test_grounding_leaves_nutrition_familiarity_none_for_providers_without_it() -> None:
    """The demo and USDA providers do not supply familiarity in `data`, so
    behaviour must be unchanged: the field stays None.
    """
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

    assert item.nutrition_familiarity is None
