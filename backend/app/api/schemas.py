from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateMealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal_request_id: UUID
    logged_at: datetime
    user_context: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_timezone(self) -> "CreateMealRequest":
        if self.logged_at.tzinfo is None:
            raise ValueError("logged_at must include a timezone offset")
        return self


class NutritionTotalsResponse(BaseModel):
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class CandidateResponse(BaseModel):
    rank: int
    source: str
    food_id: str
    name: str


class CanonicalResponse(BaseModel):
    source: str
    food_id: str
    name: str


class PortionResponse(BaseModel):
    min_g: float | None
    max_g: float | None
    confirmed_g: float | None
    resolution_source: str | None


class ConfidenceResponse(BaseModel):
    canonical: float | None


class MealItemResponse(BaseModel):
    id: UUID
    position: int
    observed_name: str
    normalized_name: str | None
    preparation_method: str | None
    canonical: CanonicalResponse | None
    candidates: list[CandidateResponse]
    portion: PortionResponse
    confidence: ConfidenceResponse
    requires_clarification: bool
    clarification_resolved: bool
    is_removed: bool
    is_user_added: bool
    nutrition: NutritionTotalsResponse | None
    review_status: str


class ClarificationResponse(BaseModel):
    id: UUID
    meal_item_id: UUID | None
    type: str
    question: str
    options: list[dict[str, Any]]
    reason_codes: list[str]
    status: str
    answer: dict[str, Any] | None
    created_at: datetime
    answered_at: datetime | None
    blocking: bool
    resolution_satisfied: bool


class CorrectionResponse(BaseModel):
    id: UUID
    meal_item_id: UUID | None
    field_name: str
    predicted_value: Any
    corrected_value: Any
    correction_source: str
    created_at: datetime


class MealResponse(BaseModel):
    id: UUID
    meal_request_id: UUID
    status: str
    image_attached: bool
    user_context: str | None
    logged_at: datetime
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    failure_code: str | None
    items: list[MealItemResponse]
    clarifications: list[ClarificationResponse]
    corrections: list[CorrectionResponse]
    totals: NutritionTotalsResponse
    review_status: str


class MealEnvelope(BaseModel):
    meal: MealResponse


class ImageAttachedResponse(BaseModel):
    meal_id: UUID
    image_attached: bool


class MealListResponse(BaseModel):
    items: list[MealResponse]
    next_cursor: str | None


class UpdateMealItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_rank: int | None = Field(default=None, ge=1)
    portion_g: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    preparation_method: str | None = Field(default=None, max_length=100)


class AddMealItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)
    portion_g: Decimal = Field(ge=0, max_digits=10, decimal_places=3)


class AnswerClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str | None = Field(default=None, max_length=100)
    custom_grams: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)

    @model_validator(mode="after")
    def exactly_one_answer(self) -> "AnswerClarificationRequest":
        if (self.option_id is None) == (self.custom_grams is None):
            raise ValueError("provide exactly one of option_id or custom_grams")
        return self


class DailySummaryResponse(BaseModel):
    date: date
    timezone: str
    totals: NutritionTotalsResponse
    meals: list[MealResponse]
