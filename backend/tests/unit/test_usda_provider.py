import json
import logging
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from app.nutrition.errors import (
    USDAAuthenticationError,
    USDAIncompleteNutritionError,
    USDAInvalidResponseError,
    USDARateLimitedError,
    USDATimeoutError,
    USDAUnavailableError,
)
from app.nutrition.providers.usda import USDAFoodDataCentralProvider


FIXTURES = Path(__file__).parents[1] / "fixtures" / "usda"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def no_sleep(_: float) -> None:
    return None


def provider_for(
    handler, *, attempts: int = 3, search_pool_size: int = 50
) -> USDAFoodDataCentralProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return USDAFoodDataCentralProvider(
        api_key="secret-test-key",
        client=client,
        max_attempts=attempts,
        search_pool_size=search_pool_size,
        sleep=no_sleep,
        jitter=lambda _start, _end: 0,
    )


@pytest.mark.asyncio
async def test_search_uses_required_identity_then_loose_fallback_and_sanitizes_metadata() -> None:
    seen_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == "secret-test-key"
        seen_bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=load_fixture("search_foods.json"),
            headers={"X-RateLimit-Limit": "1000", "X-RateLimit-Remaining": "999"},
        )

    provider = provider_for(handler)
    candidates = await provider.search_foods(
        "  Grilled Chicken Breast  ", meal_item_id=UUID(int=7), limit=2
    )

    assert seen_bodies[0]["query"] == "+chicken +breast grilled"
    assert seen_bodies[0]["pageSize"] == 50
    assert seen_bodies[0]["dataType"] == ["Foundation", "Survey (FNDDS)", "SR Legacy"]
    assert seen_bodies[1]["query"] == "chicken breast grilled"
    assert [candidate.source_food_id for candidate in candidates] == ["1001", "1002"]
    assert [candidate.rank for candidate in candidates] == [1, 2]
    assert candidates[0].source == "USDA_FDC"
    assert candidates[0].nutrition_per_100g is not None
    assert set(candidates[0].data or {}) <= {
        "data_type",
        "brand_owner",
        "serving_size",
        "serving_size_unit",
        "household_serving_full_text",
        "usda_score",
        "energy_nutrient_id",
    }
    assert provider.last_rate_limit.remaining == "999"
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_sufficient_strict_pool_skips_loose_fallback() -> None:
    seen_bodies: list[dict] = []
    foods = [
        {
            "fdcId": 9000 + index,
            "description": f"Chicken breast, grilled, sample {index}",
            "dataType": "Survey (FNDDS)",
            "score": 1,
            "foodNutrients": [],
        }
        for index in range(10)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"foods": foods})

    provider = provider_for(handler, search_pool_size=10)
    candidates = await provider.search_foods(
        "grilled chicken breast", meal_item_id=UUID(int=70), limit=2
    )

    assert len(seen_bodies) == 1
    assert seen_bodies[0]["query"] == "+chicken +breast grilled"
    assert len(candidates) == 2
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_fallback_merges_by_fdc_id_before_ranking() -> None:
    calls = 0

    def food(fdc_id: int, description: str) -> dict:
        return {
            "fdcId": fdc_id,
            "description": description,
            "dataType": "Survey (FNDDS)",
            "score": 1,
            "foodNutrients": [],
        }

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"foods": [food(1, "Olives, NFS")]})
        return httpx.Response(
            200,
            json={
                "foods": [
                    food(1, "Olives, NFS"),
                    food(2, "Olive tapenade"),
                ]
            },
        )

    provider = provider_for(handler, search_pool_size=10)
    candidates = await provider.search_foods(
        "olives", meal_item_id=UUID(int=71), limit=5
    )

    assert calls == 2
    assert [candidate.source_food_id for candidate in candidates] == ["1", "2"]
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_empty_search_response_returns_empty_candidates() -> None:
    provider = provider_for(lambda _request: httpx.Response(200, json={"foods": []}))

    assert await provider.search_foods("unknown", meal_item_id=UUID(int=8)) == []
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_requested_candidate_limit_is_applied_after_ranking() -> None:
    provider = provider_for(
        lambda _request: httpx.Response(200, json=load_fixture("search_foods.json"))
    )

    candidates = await provider.search_foods(
        "chicken breast grilled", meal_item_id=UUID(int=15), limit=1
    )

    assert len(candidates) == 1
    assert candidates[0].rank == 1
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_detail_maps_authoritative_nutrition_and_portions() -> None:
    provider = provider_for(
        lambda _request: httpx.Response(200, json=load_fixture("detail_standard.json"))
    )

    food = await provider.get_food("1001")

    assert food is not None
    assert food.source_food_id == "1001"
    assert food.nutrition_per_100g.protein_g == 31
    assert food.data == {
        "data_type": "Foundation",
        "energy_nutrient_id": 1008,
        "food_portions": [{"amount": 1, "gramWeight": 120, "modifier": "breast"}],
    }
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_detail_404_returns_none() -> None:
    provider = provider_for(lambda _request: httpx.Response(404))

    assert await provider.get_food("999") is None
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_incomplete_detail_is_not_silently_zero_filled() -> None:
    provider = provider_for(
        lambda _request: httpx.Response(
            200, json=load_fixture("incomplete_nutrition.json")
        )
    )

    with pytest.raises(USDAIncompleteNutritionError) as captured:
        await provider.get_food("3001")

    assert captured.value.details == {"missing_nutrients": ["protein"]}
    await provider._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error_type"),
    [(429, USDARateLimitedError), (502, USDAUnavailableError), (503, USDAUnavailableError), (504, USDAUnavailableError)],
)
async def test_transient_statuses_retry_then_raise(status, error_type) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, headers={"Retry-After": "0"})

    provider = provider_for(handler)
    with pytest.raises(error_type):
        await provider.search_foods("rice", meal_item_id=UUID(int=9))

    assert calls == 3
    await provider._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403])
async def test_non_transient_client_failures_do_not_retry(status: int) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    provider = provider_for(handler)
    expected = USDAAuthenticationError if status in {401, 403} else USDAInvalidResponseError
    with pytest.raises(expected):
        await provider.search_foods("rice", meal_item_id=UUID(int=10))

    assert calls == 1
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_timeout_retries_without_leaking_api_key() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("redacted", request=request)

    provider = provider_for(handler)
    with pytest.raises(USDATimeoutError) as captured:
        await provider.search_foods("rice", meal_item_id=UUID(int=11))

    assert calls == 3
    assert "secret-test-key" not in str(captured.value)
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_connection_failure_is_transient() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline", request=request)

    provider = provider_for(handler)
    with pytest.raises(USDAUnavailableError):
        await provider.search_foods("rice", meal_item_id=UUID(int=13))

    assert calls == 3
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_structured_logs_never_contain_api_key_or_raw_url(caplog) -> None:
    provider = provider_for(lambda _request: httpx.Response(503), attempts=1)

    with caplog.at_level(logging.INFO, logger="eatbetter"):
        with pytest.raises(USDAUnavailableError):
            await provider.search_foods("rice", meal_item_id=UUID(int=14))

    combined = " ".join(record.getMessage() for record in caplog.records)
    assert "secret-test-key" not in combined
    assert "api_key" not in combined
    assert "https://" not in combined
    await provider._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [httpx.Response(200, text="not-json"), httpx.Response(200, json={"unexpected": []})],
)
async def test_invalid_payload_is_classified(response: httpx.Response) -> None:
    provider = provider_for(lambda _request: response)

    with pytest.raises(USDAInvalidResponseError):
        await provider.search_foods("rice", meal_item_id=UUID(int=12))

    await provider._client.aclose()
