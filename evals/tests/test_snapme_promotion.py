import csv
import json
from pathlib import Path

import pytest

from evals.scripts.promote_snapme_recognition_manifest import build_manifest
from evals.run_recognition_benchmark import grade
from evals.dataset import DatasetManifest


def _write_inputs(tmp_path: Path, *, decision: str = "ACCEPT") -> tuple[Path, Path, Path]:
    case_id = "snapme_example"
    selection = {
        "cases": [
            {
                "case_id": case_id,
                "split": "development",
                "image": "images/example.jpg",
                "image_sha256": "a" * 64,
                "capture_date": "2022-01-05",
            },
            {
                "case_id": "snapme_holdout",
                "split": "holdout",
                "image": "images/holdout.jpg",
                "image_sha256": "b" * 64,
                "capture_date": "2022-01-06",
            },
        ]
    }
    provisional = {
        "independent_human_signoff_required": True,
        "cases": [{"case_id": case_id, "visible_labels": ["rice", "beans"]}],
    }
    selection_path = tmp_path / "selection.json"
    provisional_path = tmp_path / "provisional.json"
    signoff_path = tmp_path / "signoff.csv"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    provisional_path.write_text(json.dumps(provisional), encoding="utf-8")
    with signoff_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "proposed_visible_labels",
                "human_decision",
                "corrected_visible_labels",
                "human_reviewer",
                "reviewed_at",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "case_id": case_id,
                "proposed_visible_labels": "rice | beans",
                "human_decision": decision,
                "corrected_visible_labels": "rice | lentils" if decision == "CORRECT" else "",
                "human_reviewer": "reviewer",
                "reviewed_at": "2026-08-18",
                "notes": "subtypes not visible",
            }
        )
    return selection_path, provisional_path, signoff_path


def test_promotes_only_signed_development_recognition_labels(tmp_path: Path) -> None:
    manifest = build_manifest(*_write_inputs(tmp_path))

    assert manifest["dataset_version"] == "snapme-phone-recognition-human-reviewed-development-v1"
    assert [case["case_id"] for case in manifest["cases"]] == ["snapme_example"]
    case = manifest["cases"][0]
    assert [item["label"] for item in case["items"]] == ["rice", "beans"]
    assert all(item["portion_truth_g"] is None for item in case["items"])
    assert all(item["canonical_ground_truth_status"] == "UNVERIFIED" for item in case["items"])
    assert case["hidden_ingredients"] == []
    assert case["nutrition_truth"] is None


def test_uses_corrected_labels(tmp_path: Path) -> None:
    manifest = build_manifest(*_write_inputs(tmp_path, decision="CORRECT"))
    assert [item["label"] for item in manifest["cases"][0]["items"]] == ["rice", "lentils"]


def test_rejects_incomplete_signoff(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ACCEPT or CORRECT"):
        build_manifest(*_write_inputs(tmp_path, decision=""))


def test_recognition_only_grader_excludes_failed_cases(tmp_path: Path) -> None:
    manifest = DatasetManifest.model_validate(build_manifest(*_write_inputs(tmp_path)))
    records = [
        {
            "case_id": "snapme_example",
            "status": "completed",
            "predicted_visible_labels": ["rice", "beans"],
        }
    ]
    metrics = grade(manifest.cases, records)
    assert metrics["food_f1"]["value"] == 1.0
