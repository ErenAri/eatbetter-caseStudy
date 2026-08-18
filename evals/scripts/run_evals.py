"""Evaluation entry point. Requires labeled JSONL predictions; never invents results."""
import json
from pathlib import Path


REPORT = {
    "status": "Not measured yet",
    "baseline": "image -> LLM -> foods + estimated portions/nutrition",
    "hybrid": "vision observations -> canonical retrieval -> constrained selection -> deterministic nutrition",
    "metrics": {
        name: {"baseline": "Not measured yet", "hybrid": "Not measured yet"}
        for name in (
            "food_f1", "canonical_accuracy", "portion_mae_g", "calorie_mae_kcal",
            "calorie_mape", "macro_mae_g", "meals_within_20_percent",
            "high_confidence_wrong_rate", "clarification_rate", "user_correction_rate", "latency_ms",
        )
    },
}


if __name__ == "__main__":
    output = Path(__file__).parents[1] / "reports" / "latest.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(REPORT, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote unmeasured report to {output}")
