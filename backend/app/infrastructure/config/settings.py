from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Typed server configuration. Secret values never cross the API boundary."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnvironment = AppEnvironment.LOCAL
    app_debug: bool = False
    database_url: SecretStr | None = None
    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_storage_bucket: str = "meal-images"
    openai_api_key: SecretStr | None = None
    vision_provider: Literal["demo", "openai"] = "demo"
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: Literal["low", "medium", "high"] = "low"
    openai_image_detail: Literal["low", "high", "auto", "original"] = "high"
    openai_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    openai_max_attempts: int = Field(default=3, ge=1, le=5)
    canonicalization_provider: Literal["demo", "openai"] = "demo"
    openai_canonicalization_model: str = "gpt-5.6-terra"
    openai_canonicalization_reasoning_effort: Literal["low", "medium", "high"] = "low"
    openai_canonicalization_timeout_seconds: float = Field(default=25.0, gt=0, le=120)
    openai_canonicalization_max_attempts: int = Field(default=3, ge=1, le=5)
    usda_api_key: SecretStr | None = None
    nutrition_provider: Literal["demo", "usda", "ai"] = "demo"
    usda_base_url: str = "https://api.nal.usda.gov/fdc/v1"
    usda_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    usda_search_limit: int = Field(default=15, ge=5, le=100)
    usda_max_attempts: int = Field(default=3, ge=1, le=5)
    ai_nutrition_model: str = "gpt-5.6-terra"
    ai_nutrition_sample_count: int = Field(default=3, ge=1, le=5)
    sentry_dsn: SecretStr | None = None
    max_upload_bytes: int = Field(default=8 * 1024 * 1024, gt=0)
    allowed_mime_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
    image_retention_days: int = Field(default=7, ge=0)
    max_auto_accept_calorie_uncertainty_kcal: float = Field(default=100, ge=0)
    max_auto_accept_relative_uncertainty: float = Field(default=0.20, ge=0)

    @model_validator(mode="after")
    def require_production_configuration(self) -> "Settings":
        if self.app_env != AppEnvironment.PRODUCTION:
            return self
        if self.nutrition_provider not in ("usda", "ai"):
            raise ValueError(
                "production configuration requires NUTRITION_PROVIDER=usda or ai"
            )
        if self.vision_provider != "openai":
            raise ValueError("production configuration requires VISION_PROVIDER=openai")
        if self.canonicalization_provider != "openai":
            raise ValueError(
                "production configuration requires CANONICALIZATION_PROVIDER=openai"
            )
        required = {
            "DATABASE_URL": self.database_url,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_ANON_KEY": self.supabase_anon_key,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
            "SUPABASE_STORAGE_BUCKET": self.supabase_storage_bucket,
            "OPENAI_API_KEY": self.openai_api_key,
        }
        if self.nutrition_provider == "usda":
            required["USDA_API_KEY"] = self.usda_api_key

        def is_missing(value: object) -> bool:
            if value is None or value == "":
                return True
            return isinstance(value, SecretStr) and value.get_secret_value() == ""

        missing = [name for name, value in required.items() if is_missing(value)]
        if missing:
            raise ValueError(f"production configuration is missing: {', '.join(missing)}")
        return self

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
