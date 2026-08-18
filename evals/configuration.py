from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum


class ConfigurationName(StrEnum):
    BASELINE_TOP1 = "BASELINE_TOP1"
    HYBRID_AUTO = "HYBRID_AUTO"
    HYBRID_ORACLE_HITL = "HYBRID_ORACLE_HITL"


class BenchmarkConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ConfigurationSnapshot:
    configuration: str
    vision_provider: str
    vision_model: str
    vision_prompt_version: str
    image_detail: str
    vision_reasoning_effort: str
    retrieval_provider: str
    retrieval_search_limit: int
    retrieval_strategy: str
    canonicalization_provider: str
    canonicalization_model: str
    canonicalization_prompt_version: str
    canonicalization_reasoning_effort: str
    absolute_threshold_kcal: float
    relative_threshold: float
    dataset_version: str
    split: str
    seed: int
    timestamp_utc: str
    oracle_assisted: bool

    def to_dict(self) -> dict:
        return asdict(self)


def validate_real_providers(settings) -> None:
    errors: list[str] = []
    if settings.vision_provider != "openai" or settings.openai_api_key is None:
        errors.append("VISION_PROVIDER=openai with OPENAI_API_KEY")
    if settings.canonicalization_provider != "openai" or settings.openai_api_key is None:
        errors.append("CANONICALIZATION_PROVIDER=openai with OPENAI_API_KEY")
    if settings.nutrition_provider != "usda" or settings.usda_api_key is None:
        errors.append("NUTRITION_PROVIDER=usda with USDA_API_KEY")
    if errors:
        raise BenchmarkConfigurationError(
            "real benchmark rejected demo/unconfigured providers; required: "
            + ", ".join(errors)
        )


def snapshot(settings, *, configuration: ConfigurationName, dataset_version: str, split: str, seed: int) -> ConfigurationSnapshot:
    validate_real_providers(settings)
    return ConfigurationSnapshot(
        configuration=configuration,
        vision_provider=settings.vision_provider,
        vision_model=settings.openai_model,
        vision_prompt_version="meal_recognition_v1",
        image_detail=settings.openai_image_detail,
        vision_reasoning_effort=settings.openai_reasoning_effort,
        retrieval_provider=settings.nutrition_provider,
        retrieval_search_limit=settings.usda_search_limit,
        retrieval_strategy="normalized multi-query ranked top-5; authoritative detail after selection",
        canonicalization_provider=settings.canonicalization_provider,
        canonicalization_model=settings.openai_canonicalization_model,
        canonicalization_prompt_version="canonicalization_v1",
        canonicalization_reasoning_effort=settings.openai_canonicalization_reasoning_effort,
        absolute_threshold_kcal=settings.max_auto_accept_calorie_uncertainty_kcal,
        relative_threshold=settings.max_auto_accept_relative_uncertainty,
        dataset_version=dataset_version,
        split=split,
        seed=seed,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        oracle_assisted=configuration == ConfigurationName.HYBRID_ORACLE_HITL,
    )
