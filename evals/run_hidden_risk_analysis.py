from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.configuration import ConfigurationName
from evals.dataset import Split, load_manifest
from evals.hidden_risk_metrics import score_hidden_risk


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        case_id = value.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"missing case_id at {path}:{line_number}")
        if case_id in seen:
            raise ValueError(f"duplicate case_id in benchmark artifact: {case_id}")
        seen.add(case_id)
        records.append(value)
    return records


def _question_stage_semantics(configuration: str) -> str:
    if configuration == str(ConfigurationName.HYBRID_AUTO):
        return (
            "initial clarification state; hidden questions may be staged behind unresolved "
            "canonical/identity blockers"
        )
    if configuration == str(ConfigurationName.HYBRID_ORACLE_HITL):
        return (
            "oracle-progressed staged state; measures hidden-question reachability after resolvable "
            "earlier blockers are progressed"
        )
    return "configuration does not represent staged hybrid clarification reachability"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Score hidden-ingredient identity accuracy, hidden-risk surfacing, and question burden "
            "from an existing development benchmark artifact without new provider calls."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases-jsonl", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument(
        "--configuration",
        choices=[str(value) for value in ConfigurationName],
        default=str(ConfigurationName.HYBRID_AUTO),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("hidden-risk analysis is development-only while metrics are being validated")

    manifest_path = args.manifest.resolve()
    cases_path = args.cases_jsonl.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite hidden-risk output: {output}")

    manifest = load_manifest(manifest_path)
    cases = [case for case in manifest.cases if str(case.split) == args.split]
    records = _load_jsonl(cases_path)
    metrics = score_hidden_risk(cases, records, configuration=args.configuration)

    report = {
        "status": "measured",
        "scope": "development-only hidden ingredient identity and risk-surfacing analysis",
        "dataset_version": manifest.dataset_version,
        "split": args.split,
        "configuration": args.configuration,
        "question_stage_semantics": _question_stage_semantics(args.configuration),
        "source_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "source_cases_jsonl_sha256": sha256(cases_path.read_bytes()).hexdigest(),
        "metric_policy": {
            "identity": (
                "Exact normalized ingredient-name matching remains the identity metric. No semantic "
                "or benchmark-specific ingredient aliases are introduced."
            ),
            "risk_surface": (
                "A hidden-positive meal is risk-surfaced when the system emits any hidden-risk signal "
                "or HIDDEN_INGREDIENT question. This does not claim the ingredient identity is correct."
            ),
            "question_stage": _question_stage_semantics(args.configuration),
            "negative_burden": (
                "False-positive rates use only hidden_truth_complete meals with no present hidden "
                "ingredients, so absence is treated as a negative label only when explicitly complete."
            ),
        },
        "metrics": metrics,
        "guardrails": [
            "no provider/model calls",
            "no manifest or hidden-truth mutation",
            "no semantic ingredient equivalence or post-hoc aliases",
            "risk-surface coverage is reported separately from exact ingredient identity",
            "false-positive question burden is reported alongside coverage",
            "initial-stage and eventual-stage question coverage must not be conflated",
            "holdout is rejected while metric definitions are under development",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")

    exact = metrics["exact_recognition_recall"]
    question = metrics["question_risk_surface_case_recall"]
    false_positive = metrics["question_risk_surface_false_positive_rate"]
    print(
        "Hidden risk analysis: "
        f"exact_hidden_recall={exact['numerator']}/{exact['denominator']}; "
        f"risk_question_case_recall={question['numerator']}/{question['denominator']}; "
        f"negative_question_fp={false_positive['numerator']}/{false_positive['denominator']}"
    )
    print(f"Question stage: {_question_stage_semantics(args.configuration)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
