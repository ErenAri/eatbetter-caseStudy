from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.dataset import Split, load_manifest
from evals.hidden_risk_reachability import (
    classify_hidden_reachability,
    summarize_clarifications,
)
from evals.recognition_fixture import (
    load_recognition_fixture,
    manifest_image_hashes,
)


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
            "Trace why hidden-positive development cases do or do not reach a generated "
            "HIDDEN_INGREDIENT clarification using frozen artifacts only."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases-jsonl", type=Path, required=True)
    parser.add_argument("--frozen-recognition", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("hidden-risk reachability trace is development-only")

    manifest_path = args.manifest.resolve()
    cases_path = args.cases_jsonl.resolve()
    fixture_path = args.frozen_recognition.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite reachability trace: {output}")

    manifest = load_manifest(manifest_path)
    cases = [case for case in manifest.cases if str(case.split) == args.split]
    positive_cases = [case for case in cases if any(item.present for item in case.hidden_ingredients)]
    records = _load_jsonl(cases_path)
    records_by_id = {record["case_id"]: record for record in records}

    expected_images = manifest_image_hashes(manifest_path, cases)
    fixture = load_recognition_fixture(
        fixture_path,
        dataset_version=manifest.dataset_version,
        split=args.split,
        expected_images=expected_images,
    )
    fixture_by_id = {case.case_id: case for case in fixture.cases}

    traces = []
    for case in positive_cases:
        record = records_by_id.get(case.case_id)
        if record is None or record.get("status") != "completed":
            raise ValueError(f"hidden-positive case lacks completed benchmark record: {case.case_id}")
        configurations = record.get("configurations", {})
        auto = configurations.get("HYBRID_AUTO")
        oracle = configurations.get("HYBRID_ORACLE_HITL")
        if not isinstance(auto, dict) or not isinstance(oracle, dict):
            raise ValueError(
                f"case {case.case_id} requires HYBRID_AUTO and HYBRID_ORACLE_HITL outputs"
            )

        frozen = fixture_by_id[case.case_id]
        observation = frozen.observation.model_dump(mode="json")
        signals = list(observation.get("possible_hidden_ingredients", []))
        oracle_items = list(oracle.get("items", []))
        oracle_clarifications = list(oracle.get("clarifications", []))
        classification, details = classify_hidden_reachability(
            recognition_hidden_signals=signals,
            oracle_items=oracle_items,
            oracle_clarifications=oracle_clarifications,
        )

        traces.append(
            {
                "case_id": case.case_id,
                "hidden_truth": [
                    {
                        "name": item.name,
                        "present": item.present,
                        "calories_kcal": None if item.calories_kcal is None else float(item.calories_kcal),
                    }
                    for item in case.hidden_ingredients
                    if item.present
                ],
                "classification": classification,
                "details": details,
                "auto_clarifications": summarize_clarifications(
                    list(auto.get("clarifications", []))
                ),
                "oracle_clarifications": summarize_clarifications(oracle_clarifications),
            }
        )

    counts = Counter(trace["classification"] for trace in traces)
    report = {
        "status": "measured",
        "scope": "development-only hidden-risk clarification reachability trace",
        "dataset_version": manifest.dataset_version,
        "split": args.split,
        "positive_case_count": len(positive_cases),
        "classification_counts": dict(sorted(counts.items())),
        "cases": traces,
        "source_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "source_cases_jsonl_sha256": sha256(cases_path.read_bytes()).hexdigest(),
        "source_recognition_fixture_sha256": fixture.content_sha256,
        "guardrails": [
            "no provider/model calls",
            "development only",
            "no manifest, truth, prompt, or production-policy mutation",
            "classification explains question reachability and does not grant ingredient identity credit",
            "pending canonical/identity blockers are distinguished from an unexplained reachability gap",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")

    print(
        "Hidden risk reachability trace: "
        + "; ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    )
    for trace in traces:
        blockers = trace["details"]["pending_earlier_blockers"]
        print(
            f"{trace['case_id']}: {trace['classification']}; "
            f"eligible_hidden_signals={trace['details']['eligible_signal_count_after_visible_overlap']}; "
            f"pending_earlier_blockers={len(blockers)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
