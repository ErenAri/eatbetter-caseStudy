from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImageQualityIssue(StrEnum):
    TOO_DARK = "TOO_DARK"
    TOO_BLURRY = "TOO_BLURRY"
    FOOD_OCCLUDED = "FOOD_OCCLUDED"
    FOOD_TOO_SMALL = "FOOD_TOO_SMALL"
    MULTIPLE_MEALS = "MULTIPLE_MEALS"
    IMAGE_NOT_MEAL = "IMAGE_NOT_MEAL"
    INSUFFICIENT_VISUAL_INFORMATION = "INSUFFICIENT_VISUAL_INFORMATION"


class ObservationCertainty(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class HiddenIngredientImpact(StrEnum):
    LOW = "LOW"
    MATERIAL = "MATERIAL"
    UNKNOWN = "UNKNOWN"


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PortionEstimateSchema(StrictAIModel):
    min_g: int = Field(ge=0, le=5000)
    max_g: int = Field(ge=0, le=5000)

    @model_validator(mode="after")
    def validate_range(self) -> "PortionEstimateSchema":
        if self.max_g < self.min_g:
            raise ValueError("max_g cannot be below min_g")
        return self


class ImageQualityAssessment(StrictAIModel):
    usable: bool
    issues: list[ImageQualityIssue] = Field(default_factory=list, max_length=7)


class ObservedFood(StrictAIModel):
    observed_name: str = Field(min_length=1, max_length=200)
    preparation_method: str | None = Field(default=None, max_length=100)
    portion_estimate: PortionEstimateSchema | None = None
    observation_certainty: ObservationCertainty
    alternatives: list[str] = Field(default_factory=list, max_length=3)
    uncertainties: list[str] = Field(default_factory=list, max_length=10)
    visible_evidence: list[str] = Field(default_factory=list, max_length=10)


class PossibleHiddenIngredient(StrictAIModel):
    name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    potential_impact: HiddenIngredientImpact


class MealObservation(StrictAIModel):
    image_quality: ImageQualityAssessment
    items: list[ObservedFood] = Field(default_factory=list, max_length=20)
    possible_hidden_ingredients: list[PossibleHiddenIngredient] = Field(
        default_factory=list, max_length=10
    )
    meal_level_uncertainties: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def unusable_images_have_no_observed_foods(self) -> "MealObservation":
        if not self.image_quality.usable and self.items:
            raise ValueError("unusable images cannot contain observed food items")
        return self
