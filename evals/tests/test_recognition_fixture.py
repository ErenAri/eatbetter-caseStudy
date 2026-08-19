from __future__ import annotations

from hashlib import sha256

import pytest

from app.domain.entities import MealImage
from evals.recognition_fixture import (
    FROZEN_PROVIDER_NAME,
    FrozenVisionProvider,
    VisionConfiguration,
    load_recognition_fixture,
    write_recognition_fixture,
)


PNG = b"\x89PNG\r\n\x1a\nfixture-image"


def observation() -> dict:
    return {
        "image_quality": {"usable": True, "issues": []},
        "items": [
            {
                "observed_name": "scrambled eggs",
                "preparation_method": "scrambled",
                "portion_estimate": {"min_g": 100, "max_g": 140},
                "observation_certainty": "HIGH",
                "alternatives": ["omelet"],
                "uncertainties": ["exact egg preparation"],
                "visible_evidence": ["yellow cooked egg curds"],
            }
        ],
        "possible_hidden_ingredients": [
            {
                "name": "butter",
                "reason": "possible cooking fat",
                "potential_impact": "MATERIAL",
            }
        ],
        "meal_level_uncertainties": ["cooking fat is not visible"],
    }


@pytest.mark.asyncio
async def test_fixture_round_trip_replays_full_observation(tmp_path) -> None:
    path = tmp_path / "recognition.json"
    digest = sha256(PNG).hexdigest()
    write_recognition_fixture(
        path,
        dataset_version="dataset-v2",
        split="development",
        vision_configuration=VisionConfiguration(
            provider="openai",
            model="test-model",
            prompt_version="meal_recognition_v2",
            image_detail="high",
            reasoning_effort="low",
        ),
        expected_case_ids=["case-1"],
        records=[
            {
                "case_id": "case-1",
                "status": "completed",
                "image_sha256": digest,
                "observation": observation(),
            }
        ],
    )

    fixture = load_recognition_fixture(
        path,
        dataset_version="dataset-v2",
        split="development",
        expected_images={"case-1": digest},
    )
    provider = FrozenVisionProvider(fixture)
    result = await provider.analyze_meal(
        image=MealImage(content=PNG, mime_type="image/png"),
        user_context=None,
    )

    assert result.provider == FROZEN_PROVIDER_NAME
    assert result.model == "test-model"
    assert result.input_tokens is None
    assert result.observation.items[0].observed_name == "scrambled eggs"
    assert result.observation.items[0].portion_estimate.min_g == 100
    assert result.observation.possible_hidden_ingredients[0].name == "butter"
    assert len(fixture.content_sha256) == 64


def test_fixture_rejects_changed_image_hash(tmp_path) -> None:
    path = tmp_path / "recognition.json"
    digest = sha256(PNG).hexdigest()
    write_recognition_fixture(
        path,
        dataset_version="dataset-v2",
        split="development",
        vision_configuration=VisionConfiguration(
            provider="openai",
            model="test-model",
            prompt_version="meal_recognition_v2",
            image_detail="high",
            reasoning_effort="low",
        ),
        expected_case_ids=["case-1"],
        records=[
            {
                "case_id": "case-1",
                "status": "completed",
                "image_sha256": digest,
                "observation": observation(),
            }
        ],
    )

    with pytest.raises(ValueError, match="image hash does not match"):
        load_recognition_fixture(
            path,
            dataset_version="dataset-v2",
            split="development",
            expected_images={"case-1": "0" * 64},
        )


def test_fixture_rejects_case_set_drift(tmp_path) -> None:
    path = tmp_path / "recognition.json"
    digest = sha256(PNG).hexdigest()
    write_recognition_fixture(
        path,
        dataset_version="dataset-v2",
        split="development",
        vision_configuration=VisionConfiguration(
            provider="openai",
            model="test-model",
            prompt_version="meal_recognition_v2",
            image_detail="high",
            reasoning_effort="low",
        ),
        expected_case_ids=["case-1"],
        records=[
            {
                "case_id": "case-1",
                "status": "completed",
                "image_sha256": digest,
                "observation": observation(),
            }
        ],
    )

    with pytest.raises(ValueError, match="case ids do not match"):
        load_recognition_fixture(
            path,
            dataset_version="dataset-v2",
            split="development",
            expected_images={"case-2": digest},
        )
