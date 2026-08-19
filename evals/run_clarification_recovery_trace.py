from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.clarification_recovery import trace_recovery
from evals.dataset import Split, load_manifest


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose unresolved identity/canonical clarification recovery from an existing "
            "development benchmark artifact without provider calls."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases-jsonl", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--configuration", default="HYBRID_AUTO")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("clarification recovery trace is development-only")

    manifest_path = args.manifest.resolve()
    cases_path = args.cases_jsonl.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite clarification recovery trace: {output}")

    manifest = load_manifest(manifest_path)
    cases = [case for case in manifest.cases if str(case.split) == args.split]
    records = _load_jsonl(cases_path)
    result = trace_recovery(cases, records, configuration=args.configuration)

    report = {
        "status": "measured",
        "scope": "development-only unresolved clarification recovery trace",
        "dataset_version": manifest.dataset_version,
        "split": args.split,
        "configuration": args.configuration,
        "source_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "source_cases_jsonl_sha256": sha256(cases_path.read_bytes()).hexdigest(),
        **result,
        "guardrails": [
            "no provider/model calls",
            "no manifest, truth, alias, or FDC mutation",
            "manual search is reported separately from strict static resolvability",
            "candidate-FDC evidence is used only by the evaluator trace and is never supplied to a model",
            "holdout rejected",
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")

    counts = report["classification_counts"]
    formatted = ", ".join(f"{name}={count}" for name, count in counts.items()) or "none"
    print(
        "Clarification recovery trace: "
        f"unresolved={report['unresolved_identity_or_canonical_question_count']}; {formatted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
