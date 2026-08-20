from decimal import Decimal
from uuid import uuid4

import pytest

from app.nutrition.ai_errors import AINutritionInvalidResponseError
from app.nutrition.providers.ai_nutrition import AINutritionProvider
from app.nutrition.schemas.ai_nutrition import AINutritionOutput


class FakeClient:
    """Returns a scripted payload per call and counts invocations.

    Mirrors the real AsyncOpenAI surface used by this provider:
    `client.responses.parse(...)` returning a response object exposing
    `output_parsed`. A dict payload parses into `AINutritionOutput` (the
    happy path); a non-dict payload (e.g. a raw string) simulates the SDK
    being unable to parse the model's output into the structured schema,
    which surfaces as `output_parsed is None`.
    """

    def __init__(self, payloads: list) -> None:
        self.payloads = payloads
        self.calls = 0
        self.responses = self

    async def parse(self, **kwargs):
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return FakeResponse(payload)


class FakeResponse:
    def __init__(self, payload) -> None:
        if isinstance(payload, dict):
            self.output_parsed = AINutritionOutput.model_validate(payload)
        else:
            self.output_parsed = None
        self.output = []


def _payload(calories: str) -> dict:
    return {
        "basis": "per_100g",
        "calories_kcal": calories,
        "protein_g": "10",
        "carbs_g": "20",
        "fat_g": "5",
    }


def _provider(payloads: list, *, sample_count: int = 3) -> AINutritionProvider:
    return AINutritionProvider(
        api_key="test-key",
        sample_count=sample_count,
        client=FakeClient(payloads),
        prompt="test prompt",
    )


@pytest.mark.asyncio
async def test_search_returns_one_candidate_using_the_median_sample() -> None:
    provider = _provider([_payload("100"), _payload("300"), _payload("200")])

    candidates = await provider.search_foods("grilled chicken", meal_item_id=uuid4())

    assert len(candidates) == 1
    assert candidates[0].rank == 1
    assert candidates[0].source == "AI_ESTIMATE"
    assert candidates[0].nutrition_per_100g.calories_kcal == Decimal("200")


@pytest.mark.asyncio
async def test_provider_samples_the_model_once_per_configured_sample() -> None:
    provider = _provider([_payload("200")], sample_count=3)

    await provider.search_foods("grilled chicken", meal_item_id=uuid4())

    assert provider._client.calls == 3


@pytest.mark.asyncio
async def test_agreeing_samples_produce_high_confidence() -> None:
    provider = _provider([_payload("200")])

    candidates = await provider.search_foods("grilled chicken", meal_item_id=uuid4())

    assert Decimal(candidates[0].data["confidence"]) == Decimal("1")
    assert candidates[0].data["estimated"] is True


@pytest.mark.asyncio
async def test_disagreeing_samples_lower_confidence() -> None:
    provider = _provider([_payload("100"), _payload("200"), _payload("300")])

    candidates = await provider.search_foods("grilled chicken", meal_item_id=uuid4())

    assert Decimal(candidates[0].data["confidence"]) == Decimal("0")


@pytest.mark.asyncio
async def test_repeating_the_same_query_is_cached_and_does_not_resample() -> None:
    provider = _provider([_payload("200")])
    item = uuid4()

    first = await provider.search_foods("grilled chicken", meal_item_id=item)
    calls_after_first = provider._client.calls
    second = await provider.search_foods("Grilled  Chicken", meal_item_id=item)

    assert provider._client.calls == calls_after_first
    assert first[0].nutrition_per_100g == second[0].nutrition_per_100g


@pytest.mark.asyncio
async def test_get_food_returns_the_cached_entry_by_normalized_name() -> None:
    provider = _provider([_payload("200")])
    candidates = await provider.search_foods("grilled chicken", meal_item_id=uuid4())

    food = await provider.get_food(candidates[0].source_food_id)

    assert food is not None
    assert food.nutrition_per_100g.calories_kcal == Decimal("200")


@pytest.mark.asyncio
async def test_get_food_returns_none_for_an_unknown_id() -> None:
    provider = _provider([_payload("200")])

    assert await provider.get_food("never-requested") is None


@pytest.mark.asyncio
async def test_a_response_that_is_not_valid_json_is_rejected() -> None:
    provider = AINutritionProvider(
        api_key="test-key",
        sample_count=1,
        client=FakeClient([{}]),
        prompt="test prompt",
    )
    provider._client.payloads = ["not json"]

    with pytest.raises(AINutritionInvalidResponseError):
        await provider.search_foods("grilled chicken", meal_item_id=uuid4())


@pytest.mark.asyncio
async def test_an_empty_food_name_returns_no_candidates_without_calling_the_model() -> None:
    provider = _provider([_payload("200")])

    assert await provider.search_foods("   ", meal_item_id=uuid4()) == []
    assert provider._client.calls == 0
