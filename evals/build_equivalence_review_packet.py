from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.infrastructure.config import Settings
from app.main import create_app
from app.nutrition.errors import USDAIncompleteNutritionError
from evals.canonical_equivalence import (
    BlindedReviewPair,
    EquivalenceReviewKey,
    EquivalenceReviewPacket,
    ReviewKeyEntry,
    UnreviewableKeyEntry,
    UnreviewableReason,
    file_sha256,
    food_snapshot,
    now_utc,
    reference_goes_first,
    stable_pair_id,
    write_immutable_json,
)
from evals.dataset import CanonicalGroundTruthStatus, Split, load_manifest
from evals.recognition_metrics import normalize_food_name


BLINDNESS_NOTE = (
    "Reviewer packet intentionally omits candidate rank, system selection, match quality, "
    "benchmark errors, and which side is the frozen reference. Review equivalence only from "
    "the target food/preparation and the two FoodData Central snapshots."
)
KEY_WARNING = (
    "DO NOT SHARE THIS KEY WITH THE EQUIVALENCE REVIEWER. It reveals which FDC ID is the "
    "frozen reference and which ID came from the evaluated candidate pool."
)


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


def _pair_specs(manifest, records: dict[str, dict], *, split: str, configuration: str) -> list[dict]:
    specs: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for case in (value for value in manifest.cases if str(value.split) == split):
        record = records.get(case.case_id)
        if not record or record.get("status") != "completed":
            continue
        configurations = record.get("configurations", {})
        output = configurations.get(configuration)
        if not isinstance(output, dict):
            raise ValueError(
                f"candidate artifact lacks configuration {configuration!r} for {case.case_id}"
            )
        used_truth: set[str] = set()
        for item in output.get("items", []):
            observed_name = str(item.get("observed_name") or "")
            truth = _match_truth(observed_name, case, used_truth)
            if truth is None:
                continue
            if truth.canonical_ground_truth_status != CanonicalGroundTruthStatus.VERIFIED:
                continue
            if not truth.expected_fdc_id:
                continue
            already_accepted = {str(value) for value in truth.acceptable_canonical_ids}
            candidate_ids: list[str] = []
            for candidate in item.get("candidates", [])[:5]:
                food_id = str(candidate.get("food_id") or "")
                if not food_id or food_id in already_accepted or food_id in candidate_ids:
                    continue
                candidate_ids.append(food_id)
            for candidate_id in candidate_ids:
                key = (case.case_id, truth.item_id, candidate_id)
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    {
                        "case_id": case.case_id,
                        "item_id": truth.item_id,
                        "target_label": truth.label,
                        "target_preparation": truth.preparation,
                        "reference_fdc_id": str(truth.expected_fdc_id),
                        "candidate_fdc_id": candidate_id,
                    }
                )
    return sorted(specs, key=lambda value: (value["case_id"], value["item_id"], value["candidate_fdc_id"]))


async def _load_review_foods(provider, specs: list[dict]) -> tuple[dict[str, Any], dict[str, UnreviewableReason]]:
    """Load authoritative details while preserving a strict reference boundary.

    Frozen reference IDs are mandatory evidence: if any reference is unavailable or
    lacks complete authoritative macros, the audit cannot establish its comparison
    anchor and must fail. Non-reference candidate IDs are secondary evidence. A
    candidate that is no longer detail-resolvable is recorded as unreviewable and is
    excluded from the blinded packet; it is never counted as equivalent.
    """
    reference_ids = sorted({spec["reference_fdc_id"] for spec in specs}, key=int)
    candidate_ids = sorted({spec["candidate_fdc_id"] for spec in specs}, key=int)
    foods: dict[str, Any] = {}
    unreviewable: dict[str, UnreviewableReason] = {}

    for food_id in reference_ids:
        try:
            food = await provider.get_food(food_id)
        except USDAIncompleteNutritionError as error:
            raise ValueError(
                f"FoodData Central reference FDC {food_id} lacks complete authoritative nutrition"
            ) from error
        if food is None:
            raise ValueError(f"FoodData Central reference detail missing for FDC {food_id}")
        foods[food_id] = food

    for food_id in candidate_ids:
        if food_id in foods:
            continue
        try:
            food = await provider.get_food(food_id)
        except USDAIncompleteNutritionError:
            unreviewable[food_id] = UnreviewableReason.CANDIDATE_NUTRITION_INCOMPLETE
            continue
        if food is None:
            unreviewable[food_id] = UnreviewableReason.CANDIDATE_DETAIL_NOT_FOUND
            continue
        foods[food_id] = food

    return foods, unreviewable


async def _build(
    settings: Settings,
    *,
    manifest,
    specs: list[dict],
    manifest_sha256: str,
    candidate_artifact_sha256: str,
    split: str,
) -> tuple[EquivalenceReviewPacket, list[ReviewKeyEntry], list[UnreviewableKeyEntry]]:
    app = create_app(settings)
    provider = app.state.nutrition_provider
    if getattr(provider, "source", None) != "USDA_FDC":
        raise ValueError("canonical-equivalence evidence requires the configured USDA_FDC provider")
    try:
        foods, unreviewable_by_id = await _load_review_foods(provider, specs)
    finally:
        for value in (
            app.state.vision_provider,
            app.state.canonicalization_provider,
            app.state.nutrition_provider,
        ):
            close = getattr(value, "aclose", None)
            if close:
                await close()

    pairs: list[BlindedReviewPair] = []
    key_entries: list[ReviewKeyEntry] = []
    unreviewable_entries: list[UnreviewableKeyEntry] = []
    for spec in specs:
        pair_id = stable_pair_id(
            dataset_version=manifest.dataset_version,
            case_id=spec["case_id"],
            item_id=spec["item_id"],
            reference_fdc_id=spec["reference_fdc_id"],
            candidate_fdc_id=spec["candidate_fdc_id"],
        )
        unreviewable_reason = unreviewable_by_id.get(spec["candidate_fdc_id"])
        if unreviewable_reason is not None:
            unreviewable_entries.append(
                UnreviewableKeyEntry(
                    pair_id=pair_id,
                    case_id=spec["case_id"],
                    item_id=spec["item_id"],
                    reference_fdc_id=spec["reference_fdc_id"],
                    candidate_fdc_id=spec["candidate_fdc_id"],
                    reason=unreviewable_reason,
                )
            )
            continue

        reference = food_snapshot(foods[spec["reference_fdc_id"]])
        candidate = food_snapshot(foods[spec["candidate_fdc_id"]])
        food_a, food_b = (
            (reference, candidate)
            if reference_goes_first(pair_id)
            else (candidate, reference)
        )
        pairs.append(
            BlindedReviewPair(
                pair_id=pair_id,
                target_label=spec["target_label"],
                target_preparation=spec["target_preparation"],
                food_a=food_a,
                food_b=food_b,
            )
        )
        key_entries.append(
            ReviewKeyEntry(
                pair_id=pair_id,
                case_id=spec["case_id"],
                item_id=spec["item_id"],
                reference_fdc_id=spec["reference_fdc_id"],
                candidate_fdc_id=spec["candidate_fdc_id"],
            )
        )

    if not pairs:
        raise ValueError("no reviewable canonical-equivalence pairs remain after USDA detail validation")

    packet = EquivalenceReviewPacket(
        dataset_version=manifest.dataset_version,
        split=split,
        source_manifest_sha256=manifest_sha256,
        source_candidate_artifact_sha256=candidate_artifact_sha256,
        created_utc=now_utc(),
        blindness_note=BLINDNESS_NOTE,
        pairs=sorted(pairs, key=lambda value: value.pair_id),
    )
    return (
        packet,
        sorted(key_entries, key=lambda value: value.pair_id),
        sorted(unreviewable_entries, key=lambda value: value.pair_id),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an outcome-blinded canonical-equivalence review packet."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cases-jsonl", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--configuration", default="HYBRID_AUTO")
    parser.add_argument("--packet-output", type=Path, required=True)
    parser.add_argument("--key-output", type=Path, required=True)
    args = parser.parse_args()

    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("canonical-equivalence review packet generation is development-only")
    if args.packet_output.resolve() == args.key_output.resolve():
        raise SystemExit("review packet and private key must be written to different files")

    manifest_path = args.manifest.resolve()
    candidate_path = args.cases_jsonl.resolve()
    manifest = load_manifest(manifest_path)
    records = _load_jsonl(candidate_path)
    specs = _pair_specs(
        manifest,
        records,
        split=args.split,
        configuration=args.configuration,
    )
    if not specs:
        raise SystemExit("no non-exact VERIFIED candidate pairs were available for review")

    settings = Settings(_env_file=ROOT / "backend" / ".env")
    packet, key_entries, unreviewable_entries = asyncio.run(
        _build(
            settings,
            manifest=manifest,
            specs=specs,
            manifest_sha256=file_sha256(manifest_path),
            candidate_artifact_sha256=file_sha256(candidate_path),
            split=args.split,
        )
    )
    packet_hash = write_immutable_json(args.packet_output.resolve(), packet)
    key = EquivalenceReviewKey(
        dataset_version=manifest.dataset_version,
        split=args.split,
        review_packet_sha256=packet_hash,
        source_manifest_sha256=file_sha256(manifest_path),
        source_candidate_artifact_sha256=file_sha256(candidate_path),
        warning=KEY_WARNING,
        entries=key_entries,
        unreviewable_entries=unreviewable_entries,
    )
    write_immutable_json(args.key_output.resolve(), key)
    print(
        f"Wrote blinded equivalence packet with {len(packet.pairs)} pairs; "
        f"unreviewable={len(unreviewable_entries)}; packet_sha256={packet_hash}"
    )
    for entry in unreviewable_entries:
        print(
            "Unreviewable candidate: "
            f"case={entry.case_id} item={entry.item_id} fdc_id={entry.candidate_fdc_id} "
            f"reason={entry.reason}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
