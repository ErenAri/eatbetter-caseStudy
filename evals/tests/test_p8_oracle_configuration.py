from pathlib import Path

import pytest
from pydantic import SecretStr

from app.ai.providers.openai_vision import PROMPT_VERSION as VISION_PROMPT_VERSION
from app.infrastructure.config import Settings
from evals.configuration import BenchmarkConfigurationError, ConfigurationName, snapshot, validate_real_providers
from evals.dataset import DatasetManifest
from evals.oracle import answer_generated_clarification
from evals.reporting import write_report
from evals.tests.test_p8_dataset import manifest, valid_case


def real_settings():
    return Settings(
        vision_provider="openai", canonicalization_provider="openai", nutrition_provider="usda",
        openai_api_key=SecretStr("test-key"), usda_api_key=SecretStr("test-key"),
    )


def test_demo_providers_are_rejected():
    with pytest.raises(BenchmarkConfigurationError, match="rejected demo"):
        validate_real_providers(Settings())


def test_configuration_snapshot_has_reproducibility_fields_and_no_secrets():
    value = snapshot(real_settings(), configuration=ConfigurationName.HYBRID_AUTO, dataset_version="v1", split="development", seed=7).to_dict()
    for key in ("vision_model", "vision_prompt_version", "image_detail", "recognition_input_mode", "recognition_fixture_sha256", "retrieval_ranker", "retrieval_strategy", "canonicalization_prompt_version", "absolute_threshold_kcal", "relative_threshold", "dataset_version", "split", "timestamp_utc"):
        assert key in value
    assert value["recognition_input_mode"] == "LIVE"
    assert value["recognition_fixture_sha256"] is None
    assert value["retrieval_ranker"] == "semantic"
    assert value["retrieval_strategy"] == (
        "required-identity USDA query with bounded loose fallback; "
        "semantic/generic local rerank; top-5 after dedupe; authoritative detail after selection"
    )
    assert "api_key" not in " ".join(value)


def test_unfrozen_snapshot_records_the_live_vision_prompt_version():
    """Guards against the snapshot hardcoding a stale prompt version literal.

    A non-frozen snapshot must reflect whatever prompt the live vision provider
    actually runs, so a report or fixture can never assert a prompt version
    that was not used to produce it.
    """
    value = snapshot(real_settings(), configuration=ConfigurationName.HYBRID_AUTO, dataset_version="v1", split="development", seed=7).to_dict()
    assert value["vision_prompt_version"] == VISION_PROMPT_VERSION


def test_frozen_recognition_snapshot_uses_fixture_vision_provenance():
    value = snapshot(
        real_settings(),
        configuration=ConfigurationName.HYBRID_AUTO,
        dataset_version="v2",
        split="development",
        seed=7,
        recognition_input_mode="FROZEN",
        recognition_fixture_sha256="a" * 64,
        frozen_vision_configuration={
            "provider": "openai",
            "model": "frozen-model",
            "prompt_version": "meal_recognition_v2",
            "image_detail": "high",
            "reasoning_effort": "low",
        },
    ).to_dict()
    assert value["recognition_input_mode"] == "FROZEN"
    assert value["recognition_fixture_sha256"] == "a" * 64
    assert value["vision_model"] == "frozen-model"


def test_score_first_ranker_snapshot_is_explicitly_labeled_ablation():
    value = snapshot(
        real_settings(),
        configuration=ConfigurationName.HYBRID_AUTO,
        dataset_version="v2",
        split="development",
        seed=7,
        recognition_input_mode="FROZEN",
        recognition_fixture_sha256="b" * 64,
        retrieval_ranker="score-first-pr-b",
    ).to_dict()

    assert value["retrieval_ranker"] == "score-first-pr-b"
    assert "historical PR-B USDA-score-first local rerank ablation" in value["retrieval_strategy"]


def test_unknown_ranker_is_rejected():
    with pytest.raises(BenchmarkConfigurationError, match="unknown retrieval ranker"):
        snapshot(
            real_settings(),
            configuration=ConfigurationName.HYBRID_AUTO,
            dataset_version="v2",
            split="development",
            seed=7,
            retrieval_ranker="unknown",
        )


def test_oracle_only_answers_already_generated_representable_question():
    case = DatasetManifest.model_validate(manifest([valid_case()])).cases[0]
    generated = {"type": "CANONICAL_SELECTION", "options": [{"id": "candidate-2", "grader_food_id": "173944"}]}
    answer = answer_generated_clarification(generated, case, observed_name="fresh banana")
    assert answer.resolvable is True
    assert answer.option_id == "candidate-2"
    assert answer_generated_clarification({}, case, observed_name="banana").resolvable is False


def test_oracle_uses_true_grams_only_for_generated_portion_question():
    case = DatasetManifest.model_validate(manifest([valid_case()])).cases[0]
    answer = answer_generated_clarification({"type": "PORTION", "options": []}, case, observed_name="banana")
    assert answer.custom_grams == 100


def test_report_directory_is_immutable(tmp_path: Path):
    output = tmp_path / "run"
    manifest_value = DatasetManifest.model_validate(manifest([]))
    configurations = [snapshot(real_settings(), configuration=name, dataset_version="v1", split="development", seed=7) for name in ConfigurationName]
    write_report(output, manifest=manifest_value, cases=[], records=[], configurations=configurations)
    assert {"summary.json", "cases.jsonl", "errors.json", "metrics.json", "configuration.json", "summary.md"} <= {path.name for path in output.iterdir()}
    with pytest.raises(FileExistsError):
        write_report(output, manifest=manifest_value, cases=[], records=[], configurations=configurations)
