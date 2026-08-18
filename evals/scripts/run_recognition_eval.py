"""Create a comparable, explicitly unmeasured recognition report.

Live execution remains opt-in work for a labeled, consented image dataset.
"""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--prompt-version", default="meal_recognition_v1")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--image-detail", default="high")
    args = parser.parse_args()

    root = Path(__file__).parents[1]
    manifest = json.loads(
        (root / "datasets" / "meal_recognition" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    report = {
        "status": "Not measured yet",
        "configuration": {
            "provider": "openai",
            "model": args.model,
            "prompt_version": args.prompt_version,
            "image_detail": args.image_detail,
            "reasoning_effort": args.reasoning_effort,
        },
        "case_count": len(manifest["cases"]),
        "metrics": {
            "food_precision": None,
            "food_recall": None,
            "food_f1": None,
            "preparation_accuracy": None,
            "hallucinated_food_count": None,
            "missed_food_count": None,
            "portion_mae_g": None,
        },
        "cases": [],
    }
    output = root / "reports" / "meal_recognition_unmeasured.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote unmeasured recognition report to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
