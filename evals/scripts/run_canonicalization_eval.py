"""Emit a model-comparison-ready, unmeasured selector report."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--prompt-version", default="canonicalization_v1")
    args = parser.parse_args()

    root = Path(__file__).parents[1]
    manifest = json.loads(
        (root / "datasets" / "canonicalization" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    verified = [
        case
        for case in manifest["cases"]
        if case["expected_source_food_id"] is not None
        and case["expected_candidate_rank"] is not None
    ]
    report = {
        "status": "Not measured yet" if not verified else "Predictions not supplied",
        "configuration": {
            "provider": "openai",
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "prompt_version": args.prompt_version,
        },
        "frozen_case_count": len(manifest["cases"]),
        "verified_case_count": len(verified),
        "baselines": {"USDA_TOP_1": {"selection_accuracy": None}},
        "metrics": {
            "selection_accuracy": None,
            "selective_accuracy": None,
            "coverage": None,
            "abstention_rate": None,
            "wrong_selection_rate": None,
            "invalid_rank_rate": None,
            "wrong_strong_selection_rate": None,
        },
        "cases": [],
    }
    output = root / "reports" / "canonicalization_unmeasured.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote unmeasured canonicalization report to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
