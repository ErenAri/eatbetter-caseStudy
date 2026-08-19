from __future__ import annotations

import argparse
import asyncio
import json
import sys
from hashlib import sha256
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.ai.providers.openai_vision import OpenAIVisionProvider
from app.domain.entities import MealImage
from app.infrastructure.config import Settings
from evals.benchmark_metrics import recognition_metric_values
from evals.dataset import Split, load_manifest
from evals.recognition_metrics import ExpectedFood
from evals.recognition_segmentation import (
    aggregate_segmentation_diagnostics,
    diagnose_recognition_mismatches,
)


BASELINE_NAME = "meal_recognition_v2"
CANDIDATE_NAME = "meal_recognition_v3_experimental"
BASELINE_PROMPT = ROOT / "backend" / "app" / "ai" / "prompts" / f"{BASELINE_NAME}.md"
CANDIDATE_PROMPT = ROOT / "backend" / "app" / "ai" / "prompts" / f"{CANDIDATE_NAME}.md"


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


def balanced_variant_order(repeat_index: int, case_index: int) -> tuple[str, str]:
    """Balance which prompt is called first across repeats/cases."""
    return (
        (BASELINE_NAME, CANDIDATE_NAME)
        if (repeat_index + case_index) % 2 == 0
        else (CANDIDATE_NAME, BASELINE_NAME)
    )


def _metric(metrics: dict, name: str) -> float:
    value = metrics[name]["value"]
    if value is None:
        raise ValueError(f"recognition metric {name} is unexpectedly null")
    return float(value)


def summarize_repeats(repeats: list[dict]) -> dict:
    if not repeats:
        raise ValueError("prompt ablation requires at least one completed repeat")

    metric_names = ("food_f1", "food_precision", "food_recall")
    summary = {
        name: {
            "values": [_metric(repeat["strict_metrics"], name) for repeat in repeats],
        }
        for name in metric_names
    }
    for value in summary.values():
        value["mean"] = mean(value["values"])

    count_names = ("missed_food_count", "hallucinated_food_count")
    for name in count_names:
        values = [int(repeat["strict_metrics"][name]["value"]) for repeat in repeats]
        summary[name] = {"values": values, "mean": mean(values)}

    categories = sorted(
        {
            category
            for repeat in repeats
            for category in repeat["diagnostic_metrics"]["category_event_counts"]
        }
    )
    summary["diagnostic_event_means"] = {
        category: mean(
            repeat["diagnostic_metrics"]["category_event_counts"].get(category, 0)
            for repeat in repeats
        )
        for category in categories
    }
    summary["diagnostic_strict_error_unit_means"] = {
        category: mean(
            repeat["diagnostic_metrics"]["category_strict_error_units"].get(category, 0)
            for repeat in repeats
        )
        for category in categories
    }
    return summary


def paired_deltas(baseline: list[dict], candidate: list[dict]) -> list[dict]:
    if len(baseline) != len(candidate):
        raise ValueError("paired prompt repeats must have equal lengths")
    output = []
    for index, (base, cand) in enumerate(zip(baseline, candidate, strict=True), start=1):
        base_metrics = base["strict_metrics"]
        cand_metrics = cand["strict_metrics"]
        output.append(
            {
                "repeat": index,
                "food_f1_delta": _metric(cand_metrics, "food_f1")
                - _metric(base_metrics, "food_f1"),
                "food_precision_delta": _metric(cand_metrics, "food_precision")
                - _metric(base_metrics, "food_precision"),
                "food_recall_delta": _metric(cand_metrics, "food_recall")
                - _metric(base_metrics, "food_recall"),
                "missed_food_count_delta": int(cand_metrics["missed_food_count"]["value"])
                - int(base_metrics["missed_food_count"]["value"]),
                "hallucinated_food_count_delta": int(
                    cand_metrics["hallucinated_food_count"]["value"]
                )
                - int(base_metrics["hallucinated_food_count"]["value"]),
            }
        )
    return output


async def _analyze(
    provider: OpenAIVisionProvider,
    *,
    variant: str,
    repeat_index: int,
    case,
    image_path: Path,
) -> dict:
    image_content = image_path.read_bytes()
    started = perf_counter()
    result = await provider.analyze_meal(
        image=MealImage(content=image_content, mime_type=_mime(image_path)),
        user_context=None,
        request_id=uuid5(
            NAMESPACE_URL,
            f"vision-prompt-ablation:{variant}:{repeat_index}:{case.case_id}",
        ),
    )
    observation = result.observation
    return {
        "case_id": case.case_id,
        "predicted_visible_labels": [
            item.observed_name for item in observation.items if item.observed_name
        ],
        "observation": observation.model_dump(mode="json"),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "retry_count": result.retry_count,
    }


def _grade_repeat(cases: list, records: list[dict]) -> dict:
    by_id = {record["case_id"]: record for record in records}
    if set(by_id) != {case.case_id for case in cases}:
        raise ValueError("prompt ablation repeat does not contain the full case set")

    expected_by_case: list[list[ExpectedFood]] = []
    predicted_by_case: list[list[str]] = []
    diagnostics = []
    case_reports = []
    for case in cases:
        expected = [
            ExpectedFood(item.label, tuple(item.acceptable_aliases))
            for item in case.items
        ]
        predicted = list(by_id[case.case_id]["predicted_visible_labels"])
        diagnostic = diagnose_recognition_mismatches(expected, predicted)
        expected_by_case.append(expected)
        predicted_by_case.append(predicted)
        diagnostics.append(diagnostic)
        case_reports.append(
            {
                **by_id[case.case_id],
                "expected_visible_labels": [item.label for item in case.items],
                "diagnostic": diagnostic.as_dict(),
            }
        )

    return {
        "strict_metrics": recognition_metric_values(expected_by_case, predicted_by_case),
        "diagnostic_metrics": aggregate_segmentation_diagnostics(diagnostics),
        "cases": case_reports,
    }


async def run(settings: Settings, manifest_path: Path, cases: list, repeats: int) -> dict:
    if settings.vision_provider != "openai" or settings.openai_api_key is None:
        raise ValueError("vision prompt ablation requires VISION_PROVIDER=openai and OPENAI_API_KEY")

    prompts = {
        BASELINE_NAME: BASELINE_PROMPT.read_text(encoding="utf-8"),
        CANDIDATE_NAME: CANDIDATE_PROMPT.read_text(encoding="utf-8"),
    }
    api_key = settings.openai_api_key.get_secret_value()
    providers = {
        name: OpenAIVisionProvider(
            api_key=api_key,
            model=settings.openai_model,
            reasoning_effort=settings.openai_reasoning_effort,
            image_detail=settings.openai_image_detail,
            timeout_seconds=settings.openai_timeout_seconds,
            max_attempts=settings.openai_max_attempts,
            prompt=prompt,
        )
        for name, prompt in prompts.items()
    }
    for name, provider in providers.items():
        provider.prompt_version = name

    raw: dict[str, list[list[dict]]] = {
        BASELINE_NAME: [[] for _ in range(repeats)],
        CANDIDATE_NAME: [[] for _ in range(repeats)],
    }
    try:
        for repeat_index in range(repeats):
            for case_index, case in enumerate(cases):
                image_path = (manifest_path.parent / case.image).resolve()
                for variant in balanced_variant_order(repeat_index, case_index):
                    raw[variant][repeat_index].append(
                        await _analyze(
                            providers[variant],
                            variant=variant,
                            repeat_index=repeat_index,
                            case=case,
                            image_path=image_path,
                        )
                    )
    finally:
        for provider in providers.values():
            await provider.aclose()

    graded = {
        variant: [
            _grade_repeat(cases, repeat_records)
            for repeat_records in raw[variant]
        ]
        for variant in (BASELINE_NAME, CANDIDATE_NAME)
    }
    return {
        "variants": graded,
        "summaries": {
            variant: summarize_repeats(graded[variant])
            for variant in (BASELINE_NAME, CANDIDATE_NAME)
        },
        "paired_deltas_candidate_minus_baseline": paired_deltas(
            graded[BASELINE_NAME], graded[CANDIDATE_NAME]
        ),
        "prompt_provenance": {
            BASELINE_NAME: {
                "path": str(BASELINE_PROMPT.relative_to(ROOT)),
                "sha256": sha256(prompts[BASELINE_NAME].encode("utf-8")).hexdigest(),
            },
            CANDIDATE_NAME: {
                "path": str(CANDIDATE_PROMPT.relative_to(ROOT)),
                "sha256": sha256(prompts[CANDIDATE_NAME].encode("utf-8")).hexdigest(),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Paired development-only ablation of meal-recognition v2 vs v3 experimental."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.split != str(Split.DEVELOPMENT):
        raise SystemExit("vision prompt ablation is development-only")
    if not 1 <= args.repeats <= 5:
        raise SystemExit("--repeats must be between 1 and 5")

    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite prompt ablation output: {output}")

    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    cases = [case for case in manifest.cases if str(case.split) == args.split]
    if not cases:
        raise SystemExit("manifest has no development cases")

    settings = Settings(_env_file=ROOT / "backend" / ".env")
    measured = asyncio.run(run(settings, manifest_path, cases, args.repeats))
    report = {
        "status": "measured",
        "scope": "development-only paired live vision prompt ablation",
        "dataset_version": manifest.dataset_version,
        "split": args.split,
        "case_count": len(cases),
        "repeat_count": args.repeats,
        "design": (
            "Same development images and model settings for both prompts; prompt call order is "
            "balanced by repeat/case parity. Each repeat is graded independently so live-model "
            "sampling remains visible instead of being hidden by one aggregate run."
        ),
        "model_configuration": {
            "provider": settings.vision_provider,
            "model": settings.openai_model,
            "image_detail": settings.openai_image_detail,
            "reasoning_effort": settings.openai_reasoning_effort,
        },
        **measured,
        "guardrails": [
            "development only; no holdout calls",
            "production meal_recognition_v2 prompt is unchanged",
            "no manifest or acceptable-alias mutation",
            "candidate prompt contains no benchmark case IDs or FDC IDs",
            "strict label/alias metrics remain primary; segmentation taxonomy is diagnostic",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")

    baseline = report["summaries"][BASELINE_NAME]
    candidate = report["summaries"][CANDIDATE_NAME]
    print(
        "Vision prompt ablation complete: "
        f"cases={len(cases)} repeats={args.repeats}; "
        f"v2_mean_f1={baseline['food_f1']['mean']:.4f}; "
        f"v3_mean_f1={candidate['food_f1']['mean']:.4f}; "
        f"v2_mean_hallucinations={baseline['hallucinated_food_count']['mean']:.2f}; "
        f"v3_mean_hallucinations={candidate['hallucinated_food_count']['mean']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
