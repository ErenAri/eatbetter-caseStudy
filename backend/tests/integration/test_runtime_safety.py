import pytest

from app.infrastructure.config import AppEnvironment, Settings
from app.main import create_app


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
