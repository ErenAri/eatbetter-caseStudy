import pytest

from app.infrastructure.config.settings import AppEnvironment, Settings


def test_ai_is_an_accepted_nutrition_provider() -> None:
    settings = Settings(_env_file=None, nutrition_provider="ai")

    assert settings.nutrition_provider == "ai"


def test_sample_count_defaults_to_three() -> None:
    assert Settings(_env_file=None).ai_nutrition_sample_count == 3


def test_sample_count_of_one_is_rejected() -> None:
    """A single sample yields spread 0, so one unverified guess would report
    maximum confidence. The floor of 2 prevents that."""
    with pytest.raises(ValueError):
        Settings(_env_file=None, ai_nutrition_sample_count=1)


def test_min_relative_trigger_kcal_defaults_to_25() -> None:
    assert Settings(_env_file=None).min_relative_trigger_kcal == 25


def test_min_relative_trigger_kcal_rejects_negative() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, min_relative_trigger_kcal=-1)


def _production_kwargs(**overrides: object) -> dict:
    kwargs: dict = {
        "_env_file": None,
        "app_env": AppEnvironment.PRODUCTION,
        "database_url": "postgresql://example.invalid/eatbetter",
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "test-anon-key",
        "supabase_service_role_key": "test-service-key",
        "openai_api_key": "test-openai-key",
        "vision_provider": "openai",
        "canonicalization_provider": "openai",
        "nutrition_provider": "ai",
    }
    kwargs.update(overrides)
    return kwargs


def test_production_accepts_ai_nutrition_provider_without_usda_key() -> None:
    settings = Settings(**_production_kwargs())

    assert settings.nutrition_provider == "ai"


def test_production_still_rejects_demo_nutrition_provider() -> None:
    with pytest.raises(ValueError, match="NUTRITION_PROVIDER=usda or ai"):
        Settings(**_production_kwargs(nutrition_provider="demo"))


def test_production_usda_provider_requires_usda_api_key() -> None:
    with pytest.raises(ValueError, match="USDA_API_KEY"):
        Settings(**_production_kwargs(nutrition_provider="usda", usda_api_key=None))


def test_production_ai_provider_requires_openai_api_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(**_production_kwargs(nutrition_provider="ai", openai_api_key=None))
