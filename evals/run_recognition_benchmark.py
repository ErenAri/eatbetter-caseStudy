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

from app.infrastructure.config import Settings
from app.main import create_app
from evals.benchmark_metrics import latency_metrics, recognition_metric_values
from evals.dataset import DatasetManifest, EvaluationCase, Split, load_manifest
from evals.recognition_metrics import ExpectedFood


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


async def _run_case(service, manifest_path: Path, manifest: DatasetManifest, case: EvaluationCase) -> dict:
    started = perf_counter()
    try:
        user_id = uuid5(NAMESPACE_URL, "eatbetter-recognition-evaluator")
        meal, _ = await service.create_meal(
            user_id=user_id,
            meal_request_id=uuid5(NAMESPACE_URL, f"recognition:{manifest.dataset_version}:{case.case_id}"),
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
            request_id=uuid5(NAMESPACE_URL, f"recognition-request:{case.case_id}"),
        )
        run = next(value for value in meal.ai_runs if value.stage == "MEAL_RECOGNITION")
        items = (run.structured_output or {}).get("items", [])
        return {
            "case_id": case.case_id,
            "status": "completed",
            "predicted_visible_labels": [
                item.get("observed_name") for item in items if item.get("observed_name")
            ],
            "latency_ms": run.latency_ms,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
        }
    except Exception as error:
        return {
            "case_id": case.case_id,
            "status": "infrastructure_failure",
            "error_type": type(error).__name__,
            "error": str(error),
            "latency_ms": round((perf_counter() - started) * 1000),
        }


def grade(cases: list[EvaluationCase], records: list[dict]) -> dict:
    by_id = {record["case_id"]: record for record in records}
    completed = [case for case in cases if by_id[case.case_id]["status"] == "completed"]
    expected = [
        [ExpectedFood(item.label, tuple(item.acceptable_aliases)) for item in case.items]
        for case in completed
    ]
    predicted = [by_id[case.case_id]["predicted_visible_labels"] for case in completed]
    return recognition_metric_values(expected, predicted)


async def run(settings: Settings, manifest_path: Path, manifest: DatasetManifest, split: str) -> list[dict]:
    if settings.vision_provider != "openai" or settings.openai_api_key is None:
        raise ValueError("recognition benchmark requires VISION_PROVIDER=openai and OPENAI_API_KEY")
    app = create_app(settings)
    try:
        return [
            await _run_case(app.state.meal_service, manifest_path, manifest, case)
            for case in manifest.cases
            if str(case.split) == split
        ]
    finally:
        for provider in (
            app.state.vision_provider,
            app.state.canonicalization_provider,
            app.state.nutrition_provider,
        ):
            close = getattr(provider, "aclose", None)
            if close:
                await close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a vision-only recognition benchmark.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite benchmark output: {output}")
    manifest = load_manifest(manifest_path)
    cases = [case for case in manifest.cases if str(case.split) == args.split]
    if not cases:
        raise SystemExit(f"manifest has no {args.split} cases")
    settings = Settings(_env_file=ROOT / "backend" / ".env")
    records = asyncio.run(run(settings, manifest_path, manifest, args.split))
    completed = [record for record in records if record["status"] == "completed"]
    report = {
        "status": "measured" if len(completed) == len(cases) else "incomplete",
        "scope": "visible-food recognition only",
        "grading": "strict normalized exact label or pre-approved alias match",
        "dataset_version": manifest.dataset_version,
        "split": args.split,
        "configuration": {
            "provider": settings.vision_provider,
            "model": settings.openai_model,
            "prompt_version": "meal_recognition_v2",
            "image_detail": settings.openai_image_detail,
            "reasoning_effort": settings.openai_reasoning_effort,
        },
        "requested_case_count": len(cases),
        "completed_case_count": len(completed),
        "infrastructure_failure_count": len(cases) - len(completed),
        "metrics": grade(cases, records),
        "latency": latency_metrics({"vision": [record.get("latency_ms") for record in completed]}),
        "token_usage": {
            "input": sum(record.get("input_tokens") or 0 for record in completed),
            "output": sum(record.get("output_tokens") or 0 for record in completed),
        },
        "ineligible_metrics": [
            "portion",
            "hidden ingredients",
            "nutrition",
            "USDA retrieval",
            "canonical selection",
            "preparation",
        ],
        "cases": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(completed)}/{len(cases)} recognition cases to {output}; "
        f"status={report['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
