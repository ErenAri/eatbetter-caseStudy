from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from app.domain.entities import calculate_nutrition_for_grams
from app.domain.enums import ClarificationStatus
from app.main import create_app

from .configuration import ConfigurationName, validate_real_providers
from .dataset import DatasetManifest, EvaluationCase
from .oracle import answer_generated_clarification
from .recognition_fixture import FrozenVisionProvider, RecognitionFixture


def _number(value):
    return None if value is None else float(value)


def _nutrition(value):
    if value is None:
        return None
    return {
        "calories_kcal": _number(value.calories_kcal),
        "protein_g": _number(value.protein_g),
        "carbs_g": _number(value.carbs_g),
        "fat_g": _number(value.fat_g),
    }


def _mime(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[suffix]
    except KeyError as error:
        raise ValueError(f"unsupported evaluation image extension: {suffix}") from error


def _clarifications(meal) -> list[dict]:
    items = {item.id: item for item in meal.items}
    output = []
    for clarification in meal.clarifications:
        if clarification.status == ClarificationStatus.DISMISSED:
            continue
        observed = items.get(clarification.meal_item_id)
        options = deepcopy(list(clarification.options))
        if observed is not None:
            by_rank = {candidate.rank: candidate.source_food_id for candidate in observed.candidates}
            for option in options:
                rank = option.get("value", {}).get("candidate_rank")
                if rank in by_rank:
                    option["grader_food_id"] = by_rank[rank]
        ingredient_name = None
        if clarification.type == "HIDDEN_INGREDIENT" and options:
            ingredient_name = options[0].get("value", {}).get("name")
        output.append({
            "id": str(clarification.id),
            "type": clarification.type,
            "question": clarification.question,
            "blocking": clarification.blocking,
            "status": str(clarification.status),
            "observed_name": observed.observed_name if observed else None,
            "ingredient_name": ingredient_name,
            "options": options,
            "resolvable": None,
        })
    return output


def _meal_output(meal) -> dict:
    active = [item for item in meal.items if not item.is_removed]
    complete = all(item.final_nutrition is not None for item in active)
    return {
        "items": [
            {
                "observed_name": item.observed_name,
                "preparation_method": item.preparation_method,
                "candidates": [
                    {"rank": candidate.rank, "food_id": candidate.source_food_id, "name": candidate.name}
                    for candidate in item.candidates[:5]
                ],
                "selected_rank": item.canonical_candidate_rank,
                "selected_food_id": item.canonical_food_id,
                "selected_food_name": item.canonical_food_name,
                "match_quality": _match_quality(meal, item.id),
                "portion_min_g": _number(item.portion_estimate.min_g),
                "portion_max_g": _number(item.portion_estimate.max_g),
                "confirmed_portion_g": _number(item.confirmed_portion_g),
                "portion_resolution_source": str(item.portion_resolution_source) if item.portion_resolution_source else None,
                "nutrition": _nutrition(item.final_nutrition),
                "nutrition_per_100g": _nutrition(item.nutrition_snapshot),
                "calorie_relative_error": None,
                "removed": item.is_removed,
            }
            for item in active
        ],
        "nutrition_totals": _nutrition(meal.totals()) if complete else None,
        "clarifications": _clarifications(meal),
    }


def _match_quality(meal, item_id):
    run = next((run for run in meal.ai_runs if run.stage == "CANONICALIZATION" and run.structured_output and run.structured_output.get("meal_item_id") == str(item_id)), None)
    return run.structured_output.get("match_quality") if run else None


async def _baseline_top1(meal, nutrition_provider) -> dict:
    items = []
    totals = None
    complete = True
    for item in meal.items:
        if item.is_removed:
            continue
        candidate = next((candidate for candidate in item.candidates if candidate.rank == 1), None)
        midpoint = None
        if item.portion_estimate.min_g is not None and item.portion_estimate.max_g is not None:
            midpoint = (item.portion_estimate.min_g + item.portion_estimate.max_g) / Decimal("2")
        canonical = await nutrition_provider.get_food(candidate.source_food_id) if candidate else None
        nutrition = calculate_nutrition_for_grams(canonical.nutrition_per_100g, midpoint) if canonical and midpoint is not None else None
        complete = complete and nutrition is not None
        totals = nutrition if totals is None else totals + nutrition if nutrition is not None else totals
        items.append({
            "observed_name": item.observed_name,
            "preparation_method": item.preparation_method,
            "candidates": [{"rank": value.rank, "food_id": value.source_food_id, "name": value.name} for value in item.candidates[:5]],
            "selected_rank": 1 if candidate else None,
            "selected_food_id": candidate.source_food_id if candidate else None,
            "selected_food_name": canonical.name if canonical else None,
            "match_quality": "BASELINE_TOP1",
            "portion_min_g": _number(item.portion_estimate.min_g),
            "portion_max_g": _number(item.portion_estimate.max_g),
            "confirmed_portion_g": _number(midpoint),
            "portion_resolution_source": "BASELINE_MIDPOINT" if midpoint is not None else None,
            "nutrition": _nutrition(nutrition),
            "nutrition_per_100g": _nutrition(canonical.nutrition_per_100g) if canonical else None,
            "calorie_relative_error": None,
            "removed": False,
        })
    return {"items": items, "nutrition_totals": _nutrition(totals) if complete and totals is not None else None, "clarifications": []}


async def _apply_oracle(meal, service, case: EvaluationCase) -> tuple[object, list[dict]]:
    graded: list[dict] = []
    attempted: set[str] = set()
    for _ in range(50):
        generated = next((item for item in _clarifications(meal) if item["status"] == "PENDING" and item["id"] not in attempted), None)
        if generated is None:
            break
        attempted.add(generated["id"])
        answer = answer_generated_clarification(generated, case, observed_name=generated.get("observed_name"))
        generated["resolvable"] = answer.resolvable
        graded.append(generated)
        if not answer.resolvable:
            continue
        meal = await service.answer_clarification(
            meal_id=meal.id,
            clarification_id=next(value.id for value in meal.clarifications if str(value.id) == generated["id"]),
            user_id=meal.user_id,
            option_id=answer.option_id,
            custom_grams=answer.custom_grams,
        )
    return meal, graded


async def run_live(
    settings,
    manifest_path: Path,
    manifest: DatasetManifest,
    *,
    split: str,
    recognition_fixture: RecognitionFixture | None = None,
) -> list[dict]:
    validate_real_providers(settings)
    app = create_app(settings)
    service = app.state.meal_service
    nutrition_provider = app.state.nutrition_provider
    frozen_provider = FrozenVisionProvider(recognition_fixture) if recognition_fixture else None
    if frozen_provider is not None:
        service.recognition.vision_provider = frozen_provider
    user_id = uuid5(NAMESPACE_URL, "eatbetter-p8-evaluator")
    records: list[dict] = []
    try:
        for case in (item for item in manifest.cases if str(item.split) == split):
            started = perf_counter()
            try:
                meal, _ = await service.create_meal(
                    user_id=user_id,
                    meal_request_id=uuid5(NAMESPACE_URL, f"{manifest.dataset_version}:{case.case_id}"),
                    logged_at=datetime.now(timezone.utc),
                    user_context=None,
                )
                image_path = (manifest_path.parent / case.image).resolve()
                await service.attach_image(meal_id=meal.id, user_id=user_id, content=image_path.read_bytes(), mime_type=_mime(image_path))
                request_id = uuid5(NAMESPACE_URL, f"request:{case.case_id}")
                meal = await service.recognition.analyze(meal_id=meal.id, user_id=user_id, request_id=request_id)
                retrieval_started = perf_counter()
                for item in meal.items:
                    if not item.is_removed:
                        await service.grounding.retrieve_candidates(item)
                retrieval_latency_ms = round((perf_counter() - retrieval_started) * 1000)
                meal = await service.canonicalization.canonicalize_meal(meal, request_id=request_id)
                meal = await service.review.assess_meal(meal, request_id=request_id)
                pre = _meal_output(meal)
                baseline = await _baseline_top1(meal, nutrition_provider)
                meal, graded_questions = await _apply_oracle(meal, service, case)
                post = _meal_output(meal)
                pre["clarifications"] = graded_questions + [item for item in pre["clarifications"] if item["id"] not in {entry["id"] for entry in graded_questions}]
                stage_latency = {}
                stage_latency["vision"] = sum(run.latency_ms or 0 for run in meal.ai_runs if run.stage == "MEAL_RECOGNITION")
                stage_latency["canonicalization"] = sum(run.latency_ms or 0 for run in meal.ai_runs if run.stage == "CANONICALIZATION")
                stage_latency["retrieval"] = retrieval_latency_ms
                stage_latency["total"] = round((perf_counter() - started) * 1000)
                recognition_run = next(run for run in meal.ai_runs if run.stage == "MEAL_RECOGNITION")
                raw_recognition_items = (recognition_run.structured_output or {}).get("items", [])
                records.append({
                    "case_id": case.case_id,
                    "status": "completed",
                    "recognition_items": [
                        {"observed_name": item.get("observed_name"), "preparation_method": item.get("preparation_method")}
                        for item in raw_recognition_items
                    ],
                    "possible_hidden_ingredients": [
                        value.get("name")
                        for value in (recognition_run.structured_output or {}).get("possible_hidden_ingredients", [])
                        if value.get("name")
                    ],
                    "configurations": {
                        str(ConfigurationName.BASELINE_TOP1): baseline,
                        str(ConfigurationName.HYBRID_AUTO): pre,
                        str(ConfigurationName.HYBRID_ORACLE_HITL): post,
                    },
                    "latency_ms": stage_latency,
                    "token_usage": {
                        "input": sum(run.input_tokens for run in meal.ai_runs if run.input_tokens is not None) or None,
                        "output": sum(run.output_tokens for run in meal.ai_runs if run.output_tokens is not None) or None,
                    },
                })
            except Exception as error:
                records.append({"case_id": case.case_id, "status": "infrastructure_failure", "error_type": type(error).__name__, "error": str(error), "latency_ms": {"total": round((perf_counter() - started) * 1000)}})
    finally:
        providers = [
            app.state.vision_provider,
            app.state.canonicalization_provider,
            app.state.nutrition_provider,
        ]
        if frozen_provider is not None:
            providers.append(frozen_provider)
        for provider in providers:
            close = getattr(provider, "aclose", None)
            if close:
                await close()
    return records
