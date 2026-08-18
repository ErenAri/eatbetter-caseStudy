"""Promote independently reviewed SNAPMe labels into a recognition-only manifest.

This script intentionally excludes unreviewed holdout cases and never converts ASA24
amounts, nutrients, or recipe lines into measured image ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.dataset import DatasetManifest


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _split_labels(value: str) -> list[str]:
    labels = [label.strip() for label in value.split("|") if label.strip()]
    if not labels:
        raise ValueError("an accepted review must contain at least one visible label")
    return labels


def build_manifest(
    selection_path: Path,
    provisional_path: Path,
    signoff_path: Path,
    *,
    split: str = "development",
) -> dict:
    selection = _read_json(selection_path)
    provisional = _read_json(provisional_path)
    with signoff_path.open(encoding="utf-8-sig", newline="") as handle:
        signoffs = list(csv.DictReader(handle))

    if not provisional.get("independent_human_signoff_required"):
        raise ValueError("provisional review must retain the human sign-off guard")

    selected = {
        case["case_id"]: case
        for case in selection["cases"]
        if case["split"] == split
    }
    proposed = {case["case_id"]: case for case in provisional["cases"]}
    reviewed = {row["case_id"]: row for row in signoffs}
    if len(reviewed) != len(signoffs):
        raise ValueError("duplicate case_id in human sign-off")
    expected_ids = set(selected)
    if set(proposed) != expected_ids or set(reviewed) != expected_ids:
        raise ValueError("selection, provisional review, and sign-off case IDs must match")

    cases = []
    for case_id, source in selected.items():
        row = reviewed[case_id]
        decision = row["human_decision"].strip().upper()
        if decision not in {"ACCEPT", "CORRECT"}:
            raise ValueError(f"{case_id}: human_decision must be ACCEPT or CORRECT")
        if not row["human_reviewer"].strip() or not row["reviewed_at"].strip():
            raise ValueError(f"{case_id}: reviewer and review date are required")

        if decision == "ACCEPT":
            labels = list(proposed[case_id]["visible_labels"])
            signed_labels = _split_labels(row["proposed_visible_labels"])
            if signed_labels != labels:
                raise ValueError(f"{case_id}: signed proposal differs from provisional labels")
        else:
            labels = _split_labels(row["corrected_visible_labels"])

        category = "SIMPLE" if len(labels) == 1 else "MULTI_COMPONENT"
        items = [
            {
                "item_id": f"visible_{index:02d}",
                "label": label,
                "acceptable_aliases": [],
                "preparation": None,
                "portion_truth_g": None,
                "expected_fdc_id": None,
                "expected_fdc_name": None,
                "acceptable_fdc_ids": [],
                "canonical_ground_truth_status": "UNVERIFIED",
                "notes": "Human-reviewed visible identity only; subtype and preparation are unlabeled.",
            }
            for index, label in enumerate(labels, start=1)
        ]
        cases.append(
            {
                "case_id": case_id,
                "split": split,
                "categories": [category],
                "image": source["image"],
                "items": items,
                "hidden_ingredients": [],
                "nutrition_truth": None,
                "provenance": {
                    "captured_by": "SNAPMe participant (pseudonymized)",
                    "capture_device": None,
                    "capture_date": source["capture_date"],
                    "ground_truth_method": (
                        "Visible food identities independently accepted or corrected by a human "
                        "reviewer after a separate provisional visual pass. ASA24 amounts, nutrients, "
                        "hidden ingredients, subtypes, and preparation metadata were excluded."
                    ),
                    "consent_or_ownership": "LICENSED",
                },
                "notes": (
                    "USDA SNAPMe, CC BY-SA 4.0. Recognition-only evidence. "
                    f"Source image SHA-256: {source['image_sha256']}. "
                    f"Human review note: {row['notes'].strip() or 'none'}"
                ),
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset_version": f"snapme-phone-recognition-human-reviewed-{split}-v1",
        "cases": cases,
    }
    DatasetManifest.model_validate(manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--provisional", type=Path, required=True)
    parser.add_argument("--signoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    args = parser.parse_args()

    paths = [args.selection.resolve(), args.provisional.resolve(), args.signoff.resolve()]
    output = args.output.resolve()
    if any(path.parent != output.parent for path in paths):
        raise SystemExit("selection, review, sign-off, and output must share the subset directory")
    manifest = build_manifest(*paths, split=args.split)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest['cases'])} reviewed {args.split} cases to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
