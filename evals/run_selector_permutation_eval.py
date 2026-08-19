from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

import app.nutrition.providers.usda as usda_provider_module
from app.ai.schemas import CanonicalizationRequest
from app.infrastructure.config import Settings
from app.main import create_app
from app.nutrition.ranking import SEMANTIC_RANKER, SCORE_FIRST_PR_B_RANKER, resolve_food_ranker
from evals.configuration import validate_real_providers
from evals.dataset import CanonicalGroundTruthStatus, Split, load_manifest
from evals.recognition_fixture import FrozenVisionProvider, load_recognition_fixture, manifest_image_hashes
from evals.recognition_metrics import normalize_food_name
from evals.selector_permutation import (
    ALL_CONDITIONS,
    aggregate_item_summaries,
    candidate_input,
    permuted_candidates,
    post_gate_identity,
    selected_identity,
    summarize_item_runs,
)


def _mime(path: Path) -> str:
    try:
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }[path.suffix.lower()]
    except KeyError as error:
        raise ValueError(f"unsupported evaluation image extension: {path.suffix}") from error


def _match_truth(name: str, case, used: set[str]):
    normalized = normalize_food_name(name)
    for truth in case.items:
        if truth.item_id in used:
            continue
        accepted_names = {
            normalize_food_name(value)
            for value in (truth.label, *truth.acceptable_aliases)
        }
        if normalized in accepted_names:
            used.add(truth.item_id)
            return truth
    return None


async def _run(
    settings: Settings,
    manifest_path: Path,
    manifest,
    *,
    split: str,
    recognition_fixture,
) -> dict:
    app = create_app(settings)
    service = app.state.meal_service
    canonicalization_provider = app.state.canonicalization_provider
    frozen_provider = FrozenVisionProvider(recognition_fixture)
    service.recognition.vision_provider = frozen_provider
    user_id = uuid5(NAMESPACE_URL, "eatbetter-selector-permutation-evaluator")
    eligible_items: list[dict] = []
    skipped_items: list[dict] = []
    calls = 0
    input_tokens = 0
    output_tokens = 0
    started = perf_counter()

    try:
        for case in (value for value in manifest.cases if str(value.split) == split):
            meal, _ = await service.create_meal(
                user_id=user_id,
                meal_request_id=uuid5(
                    NAMESPACE_URL,
                    f"selector-permutation:{manifest.dataset_version}:{case.case_id}",
                ),
                logged_at=datetime.now(timezone.utc),
                user_context=None,
            )
            image_path = (manifest_path.parent / case.image).resolve()
            await service.attach_image(
                meal_id=meal.id,
                user_id=user_id,
                content=image_path.read_bytes(),
                mime_type=_mime(image_path),
            )
            meal = await service.recognition.analyze(
                meal_id=meal.id,
                user_id=user_id,
                request_id=uuid5(NAMESPACE_URL, f"selector-recognition:{case.case_id}"),
            )

            used_truth: set[str] = set()
            for item in meal.items:
                if item.is_removed:
                    continue
                await service.grounding.retrieve_candidates(item)
                truth = _match_truth(item.observed_name, case, used_truth)
                candidates = list(item.candidates[:5])
                base = {
                    "case_id": case.case_id,
                    "meal_item_position": item.position,
                    "observed_name": item.observed_name,
                    "preparation_method": item.preparation_method,
                    "base_candidates": [
                        {
                            "rank": candidate.rank,
                            "food_id": candidate.source_food_id,
                            "name": candidate.name,
                        }
                        for candidate in candidates
                    ],
                }
                if truth is None:
                    skipped_items.append({**base, "reason": "UNMATCHED_RECOGNITION"})
                    continue
                if truth.canonical_ground_truth_status != CanonicalGroundTruthStatus.VERIFIED:
                    skipped_items.append({**base, "reason": "UNVERIFIED_CANONICAL_TRUTH"})
                    continue
                acceptable_ids = {str(value) for value in truth.acceptable_canonical_ids}
                present_ids = {candidate.source_food_id for candidate in candidates}
                if not (acceptable_ids & present_ids):
                    skipped_items.append(
                        {
                            **base,
                            "reason": "TRUTH_NOT_IN_TOP5",
                            "acceptable_food_ids": sorted(acceptable_ids),
                        }
                    )
                    continue
                if len(candidates) < 2:
                    skipped_items.append({**base, "reason": "FEWER_THAN_TWO_CANDIDATES"})
                    continue

                runs: list[dict] = []
                for condition_index, condition in enumerate(ALL_CONDITIONS):
                    presented = permuted_candidates(candidates, condition)
                    request = CanonicalizationRequest(
                        meal_item_id=item.id,
                        observed_name=item.observed_name,
                        preparation_method=item.preparation_method,
                        user_context=meal.user_context,
                        candidates=[candidate_input(value) for value in presented],
                    )
                    result = await canonicalization_provider.select_candidate(
                        request=request,
                        request_id=uuid5(
                            NAMESPACE_URL,
                            f"selector:{case.case_id}:{item.position}:{condition}:{condition_index}",
                        ),
                    )
                    calls += 1
                    input_tokens += result.input_tokens or 0
                    output_tokens += result.output_tokens or 0
                    raw_identity = selected_identity(result.output, presented)
                    gated_identity = post_gate_identity(item, result.output, presented)
                    runs.append(
                        {
                            "condition": condition,
                            "presented_candidates": [
                                {
                                    "array_position": array_position,
                                    "rank": candidate.rank,
                                    "food_id": candidate.source_food_id,
                                    "name": candidate.name,
                                }
                                for array_position, candidate in enumerate(presented, start=1)
                            ],
                            "decision": str(result.output.decision),
                            "selected_candidate_rank": result.output.selected_candidate_rank,
                            "raw_selected_food_id": raw_identity,
                            "post_gate_selected_food_id": gated_identity,
                            "match_quality": str(result.output.match_quality),
                            "reason_codes": [str(value) for value in result.output.reason_codes],
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                            "retry_count": result.retry_count,
                        }
                    )

                expected_base_rank = next(
                    (
                        candidate.rank
                        for candidate in candidates
                        if candidate.source_food_id in acceptable_ids
                    ),
                    None,
                )
                item_record = {
                    **base,
                    "truth_label": truth.label,
                    "acceptable_food_ids": sorted(acceptable_ids),
                    "expected_base_rank": expected_base_rank,
                    "runs": runs,
                }
                item_record["summary"] = summarize_item_runs(runs, acceptable_ids)
                eligible_items.append(item_record)
    finally:
        for provider in (
            app.state.vision_provider,
            app.state.canonicalization_provider,
            app.state.nutrition_provider,
            frozen_provider,
        ):
            close = getattr(provider, "aclose", None)
            if close:
                await close()

    return {
        "status": "measured",
        "scope": "development-only selector permutation robustness",
        "dataset_version": manifest.dataset_version,
        "split": split,
        "recognition_input_mode": "FROZEN",
        "recognition_fixture_sha256": recognition_fixture.content_sha256,
        "canonicalization_provider": settings.canonicalization_provider,
        "canonicalization_model": settings.openai_canonicalization_model,
        "canonicalization_prompt_version": "canonicalization_v1",
        "conditions": list(ALL_CONDITIONS),
        "metrics": aggregate_item_summaries(eligible_items),
        "provider_calls": calls,
        "token_usage": {"input": input_tokens, "output": output_tokens},
        "latency_ms": round((perf_counter() - started) * 1000),
        "eligible_items": eligible_items,
        "skipped_items": skipped_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure canonical selector sensitivity to candidate order/rank labels."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--frozen-recognition", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--retrieval-ranker",
        choices=[SEMANTIC_RANKER, SCORE_FIRST_PR_B_RANKER],
        default=SCORE_FIRST_PR_B_RANKER,
    )
    args = parser.parse_args()
    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("selector permutation evaluation is development-only")

    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    selected = [case for case in manifest.cases if str(case.split) == args.split]
    if not selected:
        raise SystemExit("manifest has no development cases")
    fixture = load_recognition_fixture(
        args.frozen_recognition.resolve(),
        dataset_version=manifest.dataset_version,
        split=args.split,
        expected_images=manifest_image_hashes(manifest_path, selected),
    )
    settings = Settings(_env_file=ROOT / "backend" / ".env")
    validate_real_providers(settings)

    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite selector permutation output: {output}")

    original_ranker = usda_provider_module.rank_foods
    usda_provider_module.rank_foods = resolve_food_ranker(args.retrieval_ranker)
    try:
        report = asyncio.run(
            _run(
                settings,
                manifest_path,
                manifest,
                split=args.split,
                recognition_fixture=fixture,
            )
        )
    finally:
        usda_provider_module.rank_foods = original_ranker

    report["retrieval_ranker"] = args.retrieval_ranker
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics = report["metrics"]
    raw = metrics["raw"]
    gated = metrics["post_gate"]
    print(
        "Selector permutation evaluation: "
        f"eligible={metrics['eligible_item_count']}; "
        f"raw-control-instability={raw['control_repeat_instability']['value']}; "
        f"raw-array-sensitivity-stable={raw['array_position_sensitivity_control_stable']['value']}; "
        f"raw-rank-sensitivity-stable={raw['rank_label_sensitivity_control_stable']['value']}; "
        f"gated-array-sensitivity-stable={gated['array_position_sensitivity_control_stable']['value']}; "
        f"gated-rank-sensitivity-stable={gated['rank_label_sensitivity_control_stable']['value']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
