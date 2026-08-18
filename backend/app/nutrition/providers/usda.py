from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.entities import CanonicalFood, CanonicalFoodCandidate
from app.observability.logging import log_event

from ..errors import (
    USDAAuthenticationError,
    USDAConfigurationError,
    USDAIncompleteNutritionError,
    USDAInvalidResponseError,
    USDAProviderError,
    USDARateLimitedError,
    USDATimeoutError,
    USDAUnavailableError,
)
from ..normalization import normalize_food_query
from ..ranking import rank_foods
from ..usda_parser import ParsedUSDANutrition, parse_usda_nutrition


class USDASearchFood(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    fdc_id: int | str = Field(alias="fdcId")
    description: str
    data_type: str = Field(alias="dataType")
    brand_owner: str | None = Field(default=None, alias="brandOwner")
    serving_size: float | None = Field(default=None, alias="servingSize")
    serving_size_unit: str | None = Field(default=None, alias="servingSizeUnit")
    household_serving_full_text: str | None = Field(
        default=None, alias="householdServingFullText"
    )
    score: float | None = None
    food_nutrients: list[dict[str, Any]] = Field(default_factory=list, alias="foodNutrients")


class USDASearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    foods: list[USDASearchFood]


class USDAFoodDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    fdc_id: int | str = Field(alias="fdcId")
    description: str
    data_type: str = Field(alias="dataType")
    brand_owner: str | None = Field(default=None, alias="brandOwner")
    serving_size: float | None = Field(default=None, alias="servingSize")
    serving_size_unit: str | None = Field(default=None, alias="servingSizeUnit")
    household_serving_full_text: str | None = Field(
        default=None, alias="householdServingFullText"
    )
    food_nutrients: list[dict[str, Any]] = Field(alias="foodNutrients")
    food_portions: list[dict[str, Any]] = Field(default_factory=list, alias="foodPortions")


@dataclass(frozen=True, slots=True)
class RateLimitSnapshot:
    limit: str | None
    remaining: str | None


class USDAFoodDataCentralProvider:
    source = "USDA_FDC"
    transient_statuses = frozenset({429, 502, 503, 504})

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.nal.usda.gov/fdc/v1",
        timeout_seconds: float = 8,
        search_pool_size: int = 15,
        max_attempts: int = 3,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if not api_key:
            raise USDAConfigurationError("USDA_API_KEY is required for USDA retrieval.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)
        self._search_pool_size = min(max(search_pool_size, 5), 20)
        self._max_attempts = min(max(max_attempts, 1), 5)
        self._sleep = sleep
        self._jitter = jitter
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=self._timeout)
        self.last_rate_limit = RateLimitSnapshot(None, None)
        # httpx info logs include query strings; USDA credentials travel as a query parameter.
        logging.getLogger("httpx").setLevel(logging.WARNING)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_foods(
        self, query: str, *, meal_item_id: UUID, limit: int = 5
    ) -> list[CanonicalFoodCandidate]:
        normalized_query = normalize_food_query(query)
        if not normalized_query:
            return []
        started = perf_counter()
        payload = await self._request_json(
            "POST",
            "foods/search",
            operation="search",
            json_body={
                "query": normalized_query,
                "pageSize": max(self._search_pool_size, min(limit * 2, 20)),
                "dataType": ["Foundation", "Survey (FNDDS)", "SR Legacy"],
            },
        )
        try:
            response = USDASearchResponse.model_validate(payload)
        except ValidationError:
            self._log_failure("search", "USDA_INVALID_RESPONSE")
            raise USDAInvalidResponseError("USDA returned an invalid search response.") from None

        ranked = rank_foods(normalized_query, response.foods)[:limit]
        candidates: list[CanonicalFoodCandidate] = []
        for rank, food in enumerate(ranked, start=1):
            parsed = parse_usda_nutrition(food.food_nutrients)
            candidates.append(
                CanonicalFoodCandidate(
                    meal_item_id=meal_item_id,
                    rank=rank,
                    source=self.source,
                    source_food_id=str(food.fdc_id),
                    name=food.description,
                    data=self._candidate_metadata(food, parsed),
                    nutrition_per_100g=parsed.nutrition,
                )
            )
        log_event(
            "nutrition_search_completed",
            provider=self.source,
            query=normalized_query,
            result_count=len(candidates),
            latency_ms=round((perf_counter() - started) * 1000, 2),
            rate_limit_remaining=self.last_rate_limit.remaining,
        )
        return candidates

    async def get_food(self, source_food_id: str) -> CanonicalFood | None:
        if not source_food_id.isdigit():
            raise USDAInvalidResponseError("USDA food identifiers must be numeric.")
        started = perf_counter()
        payload = await self._request_json(
            "GET",
            f"food/{source_food_id}",
            operation="details",
            not_found_none=True,
        )
        if payload is None:
            return None
        try:
            detail = USDAFoodDetail.model_validate(payload)
        except ValidationError:
            self._log_failure("details", "USDA_INVALID_RESPONSE")
            raise USDAInvalidResponseError("USDA returned an invalid food detail response.") from None
        if str(detail.fdc_id) != source_food_id:
            self._log_failure("details", "USDA_INVALID_RESPONSE")
            raise USDAInvalidResponseError("USDA returned details for a different food.")
        parsed = parse_usda_nutrition(detail.food_nutrients)
        if parsed.nutrition is None:
            self._log_failure("details", "USDA_INCOMPLETE_NUTRITION")
            raise USDAIncompleteNutritionError(
                "USDA food details do not contain complete authoritative macros.",
                details={"missing_nutrients": list(parsed.missing_nutrients)},
            )
        log_event(
            "nutrition_food_retrieved",
            provider=self.source,
            source_food_id=str(detail.fdc_id),
            latency_ms=round((perf_counter() - started) * 1000, 2),
            rate_limit_remaining=self.last_rate_limit.remaining,
        )
        return CanonicalFood(
            source=self.source,
            source_food_id=str(detail.fdc_id),
            name=detail.description,
            nutrition_per_100g=parsed.nutrition,
            data=self._detail_metadata(detail, parsed),
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json_body: dict[str, Any] | None = None,
        not_found_none: bool = False,
    ) -> dict[str, Any] | None:
        for attempt in range(1, self._max_attempts + 1):
            failure: USDAProviderError | None = None
            retry_after: float | None = None
            try:
                response = await self._client.request(
                    method,
                    f"{self._base_url}/{path}",
                    params={"api_key": self._api_key},
                    json=json_body,
                    timeout=self._timeout,
                )
                self.last_rate_limit = RateLimitSnapshot(
                    response.headers.get("X-RateLimit-Limit"),
                    response.headers.get("X-RateLimit-Remaining"),
                )
                if response.status_code == 404 and not_found_none:
                    return None
                if response.status_code == 429:
                    failure = USDARateLimitedError("USDA rate limit was reached.")
                    retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                elif response.status_code in {502, 503, 504}:
                    failure = USDAUnavailableError("USDA is temporarily unavailable.")
                elif response.status_code in {401, 403}:
                    raise USDAAuthenticationError("USDA authentication failed.")
                elif response.status_code >= 400:
                    raise USDAInvalidResponseError("USDA rejected the request.")
                else:
                    try:
                        value = response.json()
                    except ValueError:
                        raise USDAInvalidResponseError("USDA returned invalid JSON.") from None
                    if not isinstance(value, dict):
                        raise USDAInvalidResponseError("USDA returned an unexpected JSON shape.")
                    return value
            except httpx.TimeoutException:
                failure = USDATimeoutError("USDA request timed out.")
            except httpx.ConnectError:
                failure = USDAUnavailableError("USDA connection failed.")
            except USDAProviderError as error:
                self._log_failure(operation, error.code, attempt=attempt)
                raise

            if failure is None:
                raise USDAInvalidResponseError("USDA request failed unexpectedly.")
            self._log_failure(operation, failure.code, attempt=attempt)
            if attempt >= self._max_attempts:
                raise failure from None
            delay = retry_after if retry_after is not None else (
                Decimal("0.25") * (2 ** (attempt - 1))
            )
            await self._sleep(float(delay) + self._jitter(0, 0.1))
        raise AssertionError("unreachable")

    def _log_failure(self, operation: str, category: str, *, attempt: int | None = None) -> None:
        log_event(
            "nutrition_provider_failed",
            provider=self.source,
            operation=operation,
            error_category=category,
            attempt=attempt,
            rate_limit_remaining=self.last_rate_limit.remaining,
        )

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return min(max(float(value), 0), 10)
        except ValueError:
            return None

    @staticmethod
    def _candidate_metadata(
        food: USDASearchFood, parsed: ParsedUSDANutrition
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {"data_type": food.data_type}
        optional = {
            "brand_owner": food.brand_owner,
            "serving_size": food.serving_size,
            "serving_size_unit": food.serving_size_unit,
            "household_serving_full_text": food.household_serving_full_text,
            "usda_score": food.score,
            "energy_nutrient_id": parsed.energy_nutrient_id,
        }
        metadata.update({key: value for key, value in optional.items() if value is not None})
        return metadata

    @staticmethod
    def _detail_metadata(food: USDAFoodDetail, parsed: ParsedUSDANutrition) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "data_type": food.data_type,
            "energy_nutrient_id": parsed.energy_nutrient_id,
        }
        optional = {
            "brand_owner": food.brand_owner,
            "serving_size": food.serving_size,
            "serving_size_unit": food.serving_size_unit,
            "household_serving_full_text": food.household_serving_full_text,
        }
        metadata.update({key: value for key, value in optional.items() if value is not None})
        portions = []
        for portion in food.food_portions[:20]:
            sanitized = {
                key: portion[key]
                for key in ("amount", "gramWeight", "modifier", "portionDescription")
                if key in portion
            }
            if sanitized:
                portions.append(sanitized)
        if portions:
            metadata["food_portions"] = portions
        return metadata


class UnconfiguredNutritionProvider:
    """Boot-safe local adapter that fails explicitly instead of impersonating USDA."""

    async def search_foods(self, query: str, *, meal_item_id: UUID, limit: int = 5):
        raise USDAConfigurationError("USDA retrieval is selected but USDA_API_KEY is not configured.")

    async def get_food(self, source_food_id: str):
        raise USDAConfigurationError("USDA retrieval is selected but USDA_API_KEY is not configured.")
