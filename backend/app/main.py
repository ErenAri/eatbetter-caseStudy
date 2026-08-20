from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.routes import health_router
from app.api.routes import create_router as create_meal_router
from app.ai.providers import (
    DemoCanonicalizationProvider,
    DemoVisionProvider,
    OpenAICanonicalizationProvider,
    OpenAIVisionProvider,
    UnconfiguredCanonicalizationProvider,
    UnconfiguredVisionProvider,
)
from app.application.services import (
    FoodGroundingService,
    MealCanonicalizationService,
    MealContractService,
    MealRecognitionService,
    MealReviewService,
)
from app.domain.policies import UncertaintyPolicy
from app.infrastructure.config import AppEnvironment, Settings
from app.infrastructure.storage import InMemoryPrivateStorage
from app.observability.logging import configure_logging
from app.observability.middleware import RequestContextMiddleware
from app.repositories import InMemoryMealRepository
from app.nutrition.providers import (
    AINutritionProvider,
    DemoNutritionProvider,
    USDAFoodDataCentralProvider,
    UnconfiguredAINutritionProvider,
    UnconfiguredNutritionProvider,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or Settings.from_env()
    if application_settings.app_env in {
        AppEnvironment.STAGING,
        AppEnvironment.PRODUCTION,
    }:
        raise RuntimeError(
            "Staging/production startup is blocked until verified authentication, "
            "persistent repository, and private object-storage adapters are implemented."
        )

    repository = InMemoryMealRepository()
    storage = InMemoryPrivateStorage()
    if application_settings.nutrition_provider == "demo":
        nutrition_provider = DemoNutritionProvider()
    elif application_settings.nutrition_provider == "ai":
        if application_settings.openai_api_key is None:
            nutrition_provider = UnconfiguredAINutritionProvider()
        else:
            nutrition_provider = AINutritionProvider(
                api_key=application_settings.openai_api_key.get_secret_value(),
                model=application_settings.ai_nutrition_model,
                sample_count=application_settings.ai_nutrition_sample_count,
                reasoning_effort=application_settings.openai_reasoning_effort,
                timeout_seconds=application_settings.openai_timeout_seconds,
                max_attempts=application_settings.openai_max_attempts,
            )
    elif application_settings.usda_api_key is None:
        nutrition_provider = UnconfiguredNutritionProvider()
    else:
        nutrition_provider = USDAFoodDataCentralProvider(
            api_key=application_settings.usda_api_key.get_secret_value(),
            base_url=application_settings.usda_base_url,
            timeout_seconds=application_settings.usda_timeout_seconds,
            search_pool_size=application_settings.usda_search_limit,
            max_attempts=application_settings.usda_max_attempts,
        )
    grounding_service = FoodGroundingService(nutrition_provider)
    if application_settings.vision_provider == "demo":
        vision_provider = DemoVisionProvider()
    elif application_settings.openai_api_key is None:
        vision_provider = UnconfiguredVisionProvider()
    else:
        vision_provider = OpenAIVisionProvider(
            api_key=application_settings.openai_api_key.get_secret_value(),
            model=application_settings.openai_model,
            reasoning_effort=application_settings.openai_reasoning_effort,
            image_detail=application_settings.openai_image_detail,
            timeout_seconds=application_settings.openai_timeout_seconds,
            max_attempts=application_settings.openai_max_attempts,
        )
    recognition_service = MealRecognitionService(repository, storage, vision_provider)
    if application_settings.canonicalization_provider == "demo":
        canonicalization_provider = DemoCanonicalizationProvider()
    elif application_settings.openai_api_key is None:
        canonicalization_provider = UnconfiguredCanonicalizationProvider()
    else:
        canonicalization_provider = OpenAICanonicalizationProvider(
            api_key=application_settings.openai_api_key.get_secret_value(),
            model=application_settings.openai_canonicalization_model,
            reasoning_effort=application_settings.openai_canonicalization_reasoning_effort,
            timeout_seconds=application_settings.openai_canonicalization_timeout_seconds,
            max_attempts=application_settings.openai_canonicalization_max_attempts,
        )
    canonicalization_service = MealCanonicalizationService(
        repository, grounding_service, canonicalization_provider
    )
    review_service = MealReviewService(
        repository,
        grounding_service,
        canonicalization_service,
        UncertaintyPolicy(
            max_absolute_calorie_uncertainty=Decimal(
                str(application_settings.max_auto_accept_calorie_uncertainty_kcal)
            ),
            max_relative_calorie_uncertainty=Decimal(
                str(application_settings.max_auto_accept_relative_uncertainty)
            ),
            min_relative_trigger_kcal=Decimal(
                str(application_settings.min_relative_trigger_kcal)
            ),
        ),
    )
    meal_service = MealContractService(
        repository,
        storage,
        grounding_service,
        recognition_service,
        canonicalization_service,
        review_service,
        max_upload_bytes=application_settings.max_upload_bytes,
        allowed_mime_types=application_settings.allowed_mime_types,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configure_logging()
        yield
        if isinstance(nutrition_provider, (USDAFoodDataCentralProvider, AINutritionProvider)):
            await nutrition_provider.aclose()
        if isinstance(vision_provider, OpenAIVisionProvider):
            await vision_provider.aclose()
        if isinstance(canonicalization_provider, OpenAICanonicalizationProvider):
            await canonicalization_provider.aclose()

    application = FastAPI(
        title="EatBetter Confidence-Aware Meal Logger",
        version="0.1.0",
        debug=application_settings.app_debug,
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    application.state.meal_repository = repository
    # Internal composition handles used by the isolated evaluation harness. They are never
    # exposed through the HTTP contract.
    application.state.meal_service = meal_service
    application.state.nutrition_provider = nutrition_provider
    application.state.vision_provider = vision_provider
    application.state.canonicalization_provider = canonicalization_provider
    application.state.provider_configuration = {
        "vision": application_settings.vision_provider,
        "canonicalization": application_settings.canonicalization_provider,
        "nutrition": application_settings.nutrition_provider,
    }
    selected_openai = (
        application_settings.vision_provider == "openai"
        or application_settings.canonicalization_provider == "openai"
    )
    missing_provider_key = (
        selected_openai and application_settings.openai_api_key is None
    ) or (
        application_settings.nutrition_provider == "usda"
        and application_settings.usda_api_key is None
    ) or (
        application_settings.nutrition_provider == "ai"
        and application_settings.openai_api_key is None
    )
    application.state.provider_mode = (
        "unconfigured"
        if missing_provider_key
        else "demo"
        if set(application.state.provider_configuration.values()) == {"demo"}
        else "live"
    )
    install_error_handlers(application)
    application.include_router(health_router)
    application.include_router(
        create_meal_router(
            meal_service,
            enable_dev_fixtures=application_settings.app_env
            in {AppEnvironment.LOCAL, AppEnvironment.TEST},
        )
    )
    return application


app = create_app()
