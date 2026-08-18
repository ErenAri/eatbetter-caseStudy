import json

import pytest
from pydantic import ValidationError

from evals.dataset import DatasetManifest, load_manifest


def valid_case(**changes):
    value = {
        "case_id": "meal_001",
        "split": "development",
        "categories": ["SIMPLE"],
        "image": "images/meal_001.jpg",
        "items": [{
            "item_id": "banana", "label": "banana", "acceptable_aliases": ["fresh banana"],
            "preparation": "raw", "portion_truth_g": "100", "expected_fdc_id": "173944",
            "expected_fdc_name": "Bananas, raw", "acceptable_fdc_ids": [],
            "canonical_ground_truth_status": "VERIFIED", "notes": "manually checked",
        }],
        "hidden_ingredients": [],
        "nutrition_truth": {"calories_kcal": "89", "protein_g": "1.1", "carbs_g": "22.8", "fat_g": "0.3", "measurement_method": "weighed and independently calculated"},
        "provenance": {"captured_by": "owner-1", "capture_device": None, "capture_date": "2026-08-18", "ground_truth_method": "kitchen scale and manual USDA review", "consent_or_ownership": "OWNER_CAPTURED"},
        "notes": "",
    }
    value.update(changes)
    return value


def manifest(cases):
    return {"schema_version": 1, "dataset_version": "p8-v1", "cases": cases}


def test_parses_valid_dataset_and_requires_existing_image(tmp_path):
    image = tmp_path / "images" / "meal_001.jpg"
    image.parent.mkdir()
    image.write_bytes(b"\xff\xd8\xffdata")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest([valid_case()])), encoding="utf-8")
    parsed = load_manifest(path)
    assert parsed.cases[0].items[0].portion_truth_g.as_tuple().exponent == 0


def test_missing_image_is_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest([valid_case()])), encoding="utf-8")
    with pytest.raises(ValueError, match="missing image"):
        load_manifest(path)


def test_holdout_overlap_fails_fast():
    with pytest.raises(ValidationError, match="both development and holdout"):
        DatasetManifest.model_validate(manifest([valid_case(), valid_case(split="holdout")]))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda case: case["items"].append(dict(case["items"][0])), "duplicate item_id"),
        (lambda case: case["items"][0].update(portion_truth_g="-1"), "greater than or equal to 0"),
        (lambda case: case["items"][0].update(expected_fdc_id="demo-banana"), "positive integer strings"),
        (lambda case: case.update(categories=["UNKNOWN"]), "Input should be"),
        (lambda case: case.update(split="training"), "Input should be"),
    ],
)
def test_invalid_ground_truth_is_rejected(mutation, message):
    case = valid_case()
    mutation(case)
    with pytest.raises(ValidationError, match=message):
        DatasetManifest.model_validate(manifest([case]))


def test_unmappable_cannot_smuggle_fdc_label():
    case = valid_case()
    case["items"][0]["canonical_ground_truth_status"] = "UNMAPPABLE"
    with pytest.raises(ValidationError, match="UNMAPPABLE"):
        DatasetManifest.model_validate(manifest([case]))
