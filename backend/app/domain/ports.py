from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from app.domain.entities import (
    CanonicalizationAnalysisResult,
    CanonicalFood,
    CanonicalFoodCandidate,
    Meal,
    MealImage,
    VisionAnalysisResult,
)
from app.ai.schemas import CanonicalizationRequest


class VisionProvider(Protocol):
    provider_name: str
    model: str
    prompt_version: str
    image_detail: str
    reasoning_effort: str

    async def analyze_meal(
        self,
        *,
        image: MealImage,
        user_context: str | None,
        request_id: UUID | None = None,
    ) -> VisionAnalysisResult: ...


class CanonicalizationProvider(Protocol):
    provider_name: str
    model: str
    prompt_version: str
    reasoning_effort: str

    async def select_candidate(
        self,
        *,
        request: CanonicalizationRequest,
        request_id: UUID | None = None,
    ) -> CanonicalizationAnalysisResult: ...


class NutritionProvider(Protocol):
    async def search_foods(
        self, query: str, *, meal_item_id: UUID, limit: int = 5
    ) -> list[CanonicalFoodCandidate]: ...
    async def get_food(self, source_food_id: str) -> CanonicalFood | None: ...


class MealRepository(Protocol):
    async def create(self, meal: Meal) -> tuple[Meal, bool]: ...
    async def save(self, meal: Meal) -> None: ...
    async def get_owned(self, meal_id: UUID, user_id: UUID) -> Meal | None: ...
    async def get_by_request_id(self, meal_request_id: UUID, user_id: UUID) -> Meal | None: ...
    async def list_owned(
        self,
        user_id: UUID,
        *,
        on_date: date | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Meal], str | None]: ...
    async def delete_owned(self, meal_id: UUID, user_id: UUID) -> Meal | None: ...


class StorageProvider(Protocol):
    async def put_private(self, content: bytes, mime_type: str) -> str: ...
    async def delete(self, key: str) -> None: ...
    async def get_private(self, key: str) -> tuple[bytes, str] | None: ...
