from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AINutritionOutput(BaseModel):
    """Structured nutrition for exactly 100 g of a single food.

    The upper calorie bound sits just above pure fat (884 kcal/100 g). A larger
    value means the model answered for a serving or a whole dish, not per 100 g.
    """

    model_config = ConfigDict(extra="forbid")

    basis: Literal["per_100g"]
    calories_kcal: Decimal = Field(ge=0, le=900)
    protein_g: Decimal = Field(ge=0, le=100)
    carbs_g: Decimal = Field(ge=0, le=100)
    fat_g: Decimal = Field(ge=0, le=100)
