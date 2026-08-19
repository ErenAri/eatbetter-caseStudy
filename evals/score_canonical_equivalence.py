from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.canonical_equivalence import (
    EquivalenceDecision,
    equivalent_candidate_ids_by_item,
    file_sha256,
    load_adjudications,
    load_review_key,
    load_review_packet,
    validate_adjudications,
    write_immutable_json,
)
from evals.dataset import CanonicalGroundTruthStatus, Split, load_manifest
from evals.recognition_metrics import normalize_food_name


def _load_jsonl(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        case_id = value.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"missing case_id at {path}:{line_number}")
        if case_id in records:
            raise ValueError(f"duplicate case_id in candidate artifact: {case_id}")
        records[case_id] = value
    return records


def _match_truth(observed_name: str, case, used: set[str]):
    normalized = normalize_food_name(observed_name)
    for truth in case.items:
        if truth.item_id in used:
            continue
        accepted = {
            normalize_food_name(value)
            for value in (truth.label, *truth.acceptable_aliases)
        }
        if normalized in accepted:
            used.add(truth.item_id)
            return truth
    return None


def _ratio(numerator: int, denominator: int) -> dict:
    return {
        "value": numerator / denominator if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
        "unit": "ratio",
    }


def _recall(rows: list[tuple[set[str], list[str]]], k: int) -> dict:
    hits = sum(bool(acceptable & set(ranked[:k])) for acceptable, ranked in rows)
    return _ratio(hits, len(rows))


def _validate_artifact_binding(
    *,
    manifest_path: Path,
    cases_path: Path,
    packet_path: Path,
    packet,
    key,
) -> None:
    manifest_hash = file_sha256(manifest_path)
    cases_hash = file_sha256(cases_path)
    packet_hash = file_sha256(packet_path)
    if packet.source_manifest_sha256 != manifest_hash or key.source_manifest_sha256 != manifest_hash:
        raise ValueError("equivalence artifacts were built from a different manifest")
    if (
        packet.source_candidate_artifact_sha256 != cases_hash
        or key.source_candidate_artifact_sha256 != cases_hash
    ):
        raise ValueError("equivalence artifacts were built from a different candidate artifact")
    if key.review_packet_sha256 != packet_hash:
        raise ValueError("equivalence review key does not belong to this packet")


def score(
    *,
    manifest,
    records: dict[str, dict],
    configuration: str,
    equivalent_by_item: dict[tuple[str, str], set[str]],
) -> dict:
    exact_rows: list[tuple[set[str], list[str]]] = []
    equivalence_rows: list[tuple[set[str], list[str]]] = []
    exact_selector_denominator = 0
    exact_selector_hits = 0
    equivalence_selector_denominator = 0
    equivalence_selector_hits = 0
    item_results: list[dict] = []

    for case in (value for value in manifest.cases if str(value.split) == str(Split.DEVELOPMENT)):
        record = records.get(case.case_id)
        if not record or record.get("status") != "completed":
            continue
        output = record.get("configurations", {}).get(configuration)
        if not isinstance(output, dict):
            raise ValueError(
                f"candidate artifact lacks configuration {configuration!r} for {case.case_id}"
            )
        used_truth: set[str] = set()
        for item in output.get("items", []):
            truth = _match_truth(str(item.get("observed_name") or ""), case, used_truth)
            if truth is None or truth.canonical_ground_truth_status != CanonicalGroundTruthStatus.VERIFIED:
                continue
            exact_ids = {str(value) for value in truth.acceptable_canonical_ids}
            if not exact_ids:
                continue
            secondary_ids = exact_ids | equivalent_by_item.get((case.case_id, truth.item_id), set())
            ranked = [
                str(candidate.get("food_id"))
                for candidate in item.get("candidates", [])[:5]
                if candidate.get("food_id") is not None
            ]
            selected = (
                str(item.get("selected_food_id"))
                if item.get("selected_food_id") is not None
                else None
            )
            exact_rows.append((exact_ids, ranked))
            equivalence_rows.append((secondary_ids, ranked))

            exact_evaluable = bool(exact_ids & set(ranked[:5]))
            equivalence_evaluable = bool(secondary_ids & set(ranked[:5]))
            if exact_evaluable:
                exact_selector_denominator += 1
                exact_selector_hits += selected in exact_ids
            if equivalence_evaluable:
                equivalence_selector_denominator += 1
                equivalence_selector_hits += selected in secondary_ids

            item_results.append(
                {
                    "case_id": case.case_id,
                    "item_id": truth.item_id,
                    "target_label": truth.label,
                    "exact_fdc_ids": sorted(exact_ids),
                    "adjudicated_equivalent_fdc_ids": sorted(secondary_ids - exact_ids),
                    "ranked_top5": ranked,
                    "selected_food_id": selected,
                    "exact_top5_hit": bool(exact_ids & set(ranked[:5])),
                    "equivalence_top5_hit": bool(secondary_ids & set(ranked[:5])),
                    "exact_selection_correct": selected in exact_ids if exact_evaluable else None,
                    "equivalence_selection_correct": (
                        selected in secondary_ids if equivalence_evaluable else None
                    ),
                }
            )

    return {
        "verified_matched_item_count": len(exact_rows),
        "retrieval": {
            "exact_recall_at_1": _recall(exact_rows, 1),
            "exact_recall_at_3": _recall(exact_rows, 3),
            "exact_recall_at_5": _recall(exact_rows, 5),
            "equivalence_recall_at_1": _recall(equivalence_rows, 1),
            "equivalence_recall_at_3": _recall(equivalence_rows, 3),
            "equivalence_recall_at_5": _recall(equivalence_rows, 5),
        },
        "selector": {
            "exact_accuracy": _ratio(exact_selector_hits, exact_selector_denominator),
            "equivalence_accuracy": _ratio(
                equivalence_selector_hits, equivalence_selector_denominator
            ),
            "exact_evaluable_item_count": exact_selector_denominator,
            "equivalence_evaluable_item_count": equivalence_selector_denominator,
        },
        "items": item_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Score a development candidate artifact with frozen exact-FDC truth plus a separately "
            "adjudicated canonical-equivalence secondary metric."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases-jsonl", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--configuration", default="HYBRID_AUTO")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    cases_path = args.cases_jsonl.resolve()
    packet_path = args.packet.resolve()
    key_path = args.key.resolve()
    adjudication_path = args.adjudications.resolve()

    manifest = load_manifest(manifest_path)
    packet = load_review_packet(packet_path)
    key = load_review_key(key_path)
    adjudications = load_adjudications(adjudication_path)
    _validate_artifact_binding(
        manifest_path=manifest_path,
        cases_path=cases_path,
        packet_path=packet_path,
        packet=packet,
        key=key,
    )
    validate_adjudications(
        packet=packet,
        packet_sha256=file_sha256(packet_path),
        key=key,
        adjudications=adjudications,
    )
    if packet.dataset_version != manifest.dataset_version:
        raise ValueError("review packet dataset differs from manifest")

    decisions = Counter(str(value.decision) for value in adjudications.adjudications)
    result = {
        "status": "measured-secondary",
        "dataset_version": manifest.dataset_version,
        "split": "development",
        "configuration": args.configuration,
        "metric_policy": (
            "Frozen exact-FDC metrics remain unchanged. EQUIVALENT adjudications expand only the "
            "secondary metric; NOT_EQUIVALENT and UNCERTAIN never count as matches."
        ),
        "review_packet_sha256": file_sha256(packet_path),
        "reviewer": adjudications.reviewer,
        "adjudication_counts": dict(sorted(decisions.items())),
        "metrics": score(
            manifest=manifest,
            records=_load_jsonl(cases_path),
            configuration=args.configuration,
            equivalent_by_item=equivalent_candidate_ids_by_item(key, adjudications),
        ),
    }
    write_immutable_json(args.output.resolve(), result)
    print(
        "Equivalence-aware scoring complete; exact metrics were preserved and secondary metrics "
        "were written separately."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
