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
    recognition_input_mode: str
    recognition_fixture_sha256: str | None
    retrieval_provider: str
    retrieval_search_limit: int
    retrieval_ranker: str
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


def snapshot(
    settings,
    *,
    configuration: ConfigurationName,
    dataset_version: str,
    split: str,
    seed: int,
    recognition_input_mode: str = "LIVE",
    recognition_fixture_sha256: str | None = None,
    frozen_vision_configuration: dict[str, str] | None = None,
    retrieval_ranker: str = "semantic",
) -> ConfigurationSnapshot:
    validate_real_providers(settings)
    vision = frozen_vision_configuration or {
        "provider": settings.vision_provider,
        "model": settings.openai_model,
        "prompt_version": "meal_recognition_v2",
        "image_detail": settings.openai_image_detail,
        "reasoning_effort": settings.openai_reasoning_effort,
    }
    if retrieval_ranker == "semantic":
        ranker_description = "semantic/generic local rerank"
    elif retrieval_ranker == "score-first-pr-b":
        ranker_description = "historical PR-B USDA-score-first local rerank ablation"
    else:
        raise BenchmarkConfigurationError(
            f"unknown retrieval ranker: {retrieval_ranker}"
        )
    return ConfigurationSnapshot(
        configuration=configuration,
        vision_provider=vision["provider"],
        vision_model=vision["model"],
        vision_prompt_version=vision["prompt_version"],
        image_detail=vision["image_detail"],
        vision_reasoning_effort=vision["reasoning_effort"],
        recognition_input_mode=recognition_input_mode,
        recognition_fixture_sha256=recognition_fixture_sha256,
        retrieval_provider=settings.nutrition_provider,
        retrieval_search_limit=settings.usda_search_limit,
        retrieval_ranker=retrieval_ranker,
        retrieval_strategy=(
            "required-identity USDA query with bounded loose fallback; "
            f"{ranker_description}; top-5 after dedupe; authoritative detail after selection"
        ),
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
