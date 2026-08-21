from uuid import uuid4

import pytest

from app.infrastructure.config import AppEnvironment, Settings
from app.main import create_app
from app.nutrition.ai_errors import AINutritionConfigurationError
from app.nutrition.providers import AINutritionProvider, UnconfiguredAINutritionProvider


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        database_url="postgresql://example.invalid/eatbetter",
        supabase_url="https://example.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-key",
        openai_api_key="test-openai-key",
        usda_api_key="test-usda-key",
        vision_provider="openai",
        canonicalization_provider="openai",
        nutrition_provider="usda",
    )


@pytest.mark.parametrize(
    "settings",
    [
        Settings(_env_file=None, app_env=AppEnvironment.STAGING),
        production_settings(),
    ],
)
def test_nonlocal_runtime_fails_closed_without_production_adapters(
    settings: Settings,
) -> None:
    with pytest.raises(RuntimeError, match="startup is blocked"):
        create_app(settings)


def test_local_and_test_runtime_composition_remains_available() -> None:
    assert create_app(Settings(_env_file=None, app_env=AppEnvironment.LOCAL))
    assert create_app(Settings(_env_file=None, app_env=AppEnvironment.TEST))


def test_local_ai_nutrition_provider_wiring_is_live() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.LOCAL,
        nutrition_provider="ai",
        openai_api_key="test-openai-key",
    )

    application = create_app(settings)

    assert isinstance(application.state.nutrition_provider, AINutritionProvider)
    assert application.state.provider_mode == "live"


def test_ai_nutrition_without_a_key_wires_the_ai_unconfigured_provider() -> None:
    """Selecting NUTRITION_PROVIDER=ai without OPENAI_API_KEY must fail with an AI
    nutrition error, not a USDA one impersonating the wrong provider."""
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.LOCAL,
        nutrition_provider="ai",
        openai_api_key=None,
    )

    application = create_app(settings)

    assert isinstance(application.state.nutrition_provider, UnconfiguredAINutritionProvider)
    assert application.state.provider_mode == "unconfigured"


@pytest.mark.asyncio
async def test_ai_unconfigured_provider_raises_an_accurate_ai_error() -> None:
    provider = UnconfiguredAINutritionProvider()

    with pytest.raises(AINutritionConfigurationError, match="OPENAI_API_KEY"):
        await provider.search_foods("banana", meal_item_id=uuid4())

    with pytest.raises(AINutritionConfigurationError, match="OPENAI_API_KEY"):
        await provider.get_food("banana")
