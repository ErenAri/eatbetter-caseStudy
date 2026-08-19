from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.benchmark_metrics import recognition_metric_values
from evals.dataset import Split, load_manifest
from evals.recognition_fixture import load_recognition_fixture, manifest_image_hashes
from evals.recognition_metrics import ExpectedFood
from evals.recognition_segmentation import (
    aggregate_segmentation_diagnostics,
    diagnose_recognition_mismatches,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explain strict visible-food recognition mismatches using a conservative "
            "lexical segmentation taxonomy. Primary recognition metrics are unchanged."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--frozen-recognition", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("recognition segmentation diagnostics are development-only")

    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    cases = [case for case in manifest.cases if str(case.split) == args.split]
    if not cases:
        raise SystemExit("manifest has no development cases")

    fixture = load_recognition_fixture(
        args.frozen_recognition.resolve(),
        dataset_version=manifest.dataset_version,
        split=args.split,
        expected_images=manifest_image_hashes(manifest_path, cases),
    )
    fixture_by_case = {case.case_id: case for case in fixture.cases}

    strict_expected: list[list[ExpectedFood]] = []
    strict_predicted: list[list[str]] = []
    case_reports: list[dict] = []
    diagnostics = []

    for case in cases:
        frozen = fixture_by_case[case.case_id]
        expected = [
            ExpectedFood(item.label, tuple(item.acceptable_aliases))
            for item in case.items
        ]
        predicted = [
            item.observed_name
            for item in frozen.observation.items
            if item.observed_name
        ]
        diagnostic = diagnose_recognition_mismatches(expected, predicted)
        strict_expected.append(expected)
        strict_predicted.append(predicted)
        diagnostics.append(diagnostic)
        case_reports.append(
            {
                "case_id": case.case_id,
                "expected_visible_labels": [item.label for item in case.items],
                "predicted_visible_labels": predicted,
                "diagnostic": diagnostic.as_dict(),
            }
        )

    report = {
        "status": "measured",
        "scope": "development-only frozen visible-food segmentation diagnostics",
        "dataset_version": manifest.dataset_version,
        "split": args.split,
        "recognition_fixture_sha256": fixture.content_sha256,
        "vision_configuration": {
            "provider": fixture.vision_configuration.provider,
            "model": fixture.vision_configuration.model,
            "prompt_version": fixture.vision_configuration.prompt_version,
            "image_detail": fixture.vision_configuration.image_detail,
            "reasoning_effort": fixture.vision_configuration.reasoning_effort,
        },
        "primary_strict_metrics_unchanged": recognition_metric_values(
            strict_expected, strict_predicted
        ),
        "diagnostic_metrics": aggregate_segmentation_diagnostics(diagnostics),
        "cases": case_reports,
        "methodology": {
            "primary_metric_policy": (
                "Strict normalized exact label or pre-approved alias matching remains primary."
            ),
            "diagnostic_policy": (
                "Exact/alias matches are removed first. Residual relationships use only the "
                "primary expected label, so broad acceptable aliases such as rice, salad, or "
                "greens are not promoted into semantic evidence. Conservative lexical "
                "containment/overlap only; no new aliases or equivalences are inferred."
            ),
            "interpretation": (
                "UNDER_SEGMENTATION and OVER_SEGMENTATION describe direct granularity events; "
                "COMPOSITE_ALIAS_WITH_EXTRA_PREDICTIONS records a neutral single-composite "
                "pattern after an accepted broader alias; IDENTITY_WITH_EXTRA_MODIFIERS and "
                "BROADER_LABEL are primary-label containment mismatches; "
                "PARTIAL_IDENTITY_OVERLAP records shared primary wording without asserting "
                "equivalence. UNEXPLAINED categories require separate semantic/image review."
            ),
        },
    }

    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite segmentation diagnostic output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    values = report["diagnostic_metrics"]
    print(
        "Recognition segmentation diagnostics: "
        f"cases={values['case_count']}; "
        f"strict_error_units={values['strict_error_units']}; "
        f"structural_events={values['structural_event_count']}"
    )
    for category, count in values["category_event_counts"].items():
        print(f"{category}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
