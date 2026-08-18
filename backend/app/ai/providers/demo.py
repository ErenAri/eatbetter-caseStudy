from uuid import UUID

from app.ai.schemas import (
    HiddenIngredientImpact,
    ImageQualityAssessment,
    MealObservation,
    ObservationCertainty,
    ObservedFood,
    PortionEstimateSchema,
    PossibleHiddenIngredient,
)
from app.domain.entities import MealImage, VisionAnalysisResult


class DemoVisionProvider:
    """Deterministic TEST DATA; never presented as an OpenAI result."""

    provider_name = "TEST_DATA"
    model = "deterministic-meal-observation"
    prompt_version = "meal_recognition_v1"
    image_detail = "high"
    reasoning_effort = "low"

    def __init__(self) -> None:
        self.call_count = 0

    async def analyze_meal(
        self,
        *,
        image: MealImage,
        user_context: str | None,
        request_id: UUID | None = None,
    ) -> VisionAnalysisResult:
        self.call_count += 1
        observation = MealObservation(
            image_quality=ImageQualityAssessment(usable=True, issues=[]),
            items=[
                ObservedFood(
                    observed_name="chicken breast",
                    preparation_method="grilled",
                    portion_estimate=PortionEstimateSchema(min_g=120, max_g=200),
                    observation_certainty=ObservationCertainty.HIGH,
                    alternatives=[],
                    uncertainties=["exact portion size"],
                    visible_evidence=["cooked chicken pieces with grill marks"],
                ),
                ObservedFood(
                    observed_name="white rice",
                    preparation_method="cooked",
                    portion_estimate=PortionEstimateSchema(min_g=140, max_g=220),
                    observation_certainty=ObservationCertainty.HIGH,
                    alternatives=["basmati rice", "jasmine rice"],
                    uncertainties=["rice variety", "portion size"],
                    visible_evidence=["white cooked rice grains"],
                ),
                ObservedFood(
                    observed_name="broccoli",
                    preparation_method=None,
                    portion_estimate=PortionEstimateSchema(min_g=50, max_g=100),
                    observation_certainty=ObservationCertainty.HIGH,
                    alternatives=[],
                    uncertainties=["preparation method"],
                    visible_evidence=["green broccoli florets"],
                ),
            ],
            possible_hidden_ingredients=[
                PossibleHiddenIngredient(
                    name="cooking oil",
                    reason="cooking fat amount cannot be determined from the image",
                    potential_impact=HiddenIngredientImpact.MATERIAL,
                )
            ],
            meal_level_uncertainties=["exact ingredient quantities"],
        )
        return VisionAnalysisResult(
            observation=observation,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            image_detail=self.image_detail,
            reasoning_effort=self.reasoning_effort,
        )


class UnconfiguredVisionProvider:
    provider_name = "OPENAI"
    model = "unconfigured"
    prompt_version = "meal_recognition_v1"
    image_detail = "high"
    reasoning_effort = "low"

    async def analyze_meal(self, **_: object) -> VisionAnalysisResult:
        from app.ai.errors import VisionConfigurationError

        raise VisionConfigurationError(
            "OpenAI vision is selected but OPENAI_API_KEY is not configured."
        )
