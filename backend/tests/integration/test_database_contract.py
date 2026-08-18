from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.entities import Meal, MealItem
from app.repositories import InMemoryMealRepository


@pytest.mark.asyncio
async def test_repository_enforces_user_scoped_idempotency_and_ownership():
    repository = InMemoryMealRepository()
    owner = uuid4()
    request_id = uuid4()
    first, replay1 = await repository.create(
        Meal(owner, request_id, datetime.now(timezone.utc))
    )
    second, replay2 = await repository.create(
        Meal(owner, request_id, datetime.now(timezone.utc))
    )
    other_user, replay3 = await repository.create(
        Meal(uuid4(), request_id, datetime.now(timezone.utc))
    )
    assert first.id == second.id
    assert replay1 is False and replay2 is True and replay3 is False
    assert other_user.id != first.id
    assert await repository.get_owned(first.id, uuid4()) is None


@pytest.mark.asyncio
async def test_repository_delete_cascades_aggregate_children():
    repository = InMemoryMealRepository()
    owner = uuid4()
    meal, _ = await repository.create(Meal(owner, uuid4(), datetime.now(timezone.utc)))
    meal.items.append(MealItem(meal.id, 0, "rice"))
    removed = await repository.delete_owned(meal.id, owner)
    assert removed is meal
    assert removed.items
    assert await repository.get_owned(meal.id, owner) is None


def test_postgres_migration_contains_required_constraints_and_cascades():
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "001_p2_authoritative_schema.sql"
    ).read_text(encoding="utf-8").lower()
    required_fragments = (
        "unique (user_id, meal_request_id)",
        "unique (meal_id, position)",
        "unique (meal_item_id, rank)",
        "on delete cascade",
        "canonical_confidence between 0 and 1",
        "portion_max_g >= portion_min_g",
        "enable row level security",
    )
    assert all(fragment in migration for fragment in required_fragments)


def test_p4_migration_adds_reproducible_vision_configuration():
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "002_p4_vision_run_metadata.sql"
    ).read_text(encoding="utf-8").lower()
    assert "image_detail" in migration
    assert "reasoning_effort" in migration
    assert "retry_count" in migration


def test_p6_migration_adds_resolution_and_idempotency_metadata():
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "003_p6_uncertainty_review.sql"
    ).read_text(encoding="utf-8").lower()
    assert "observation_certainty" in migration
    assert "portion_resolution_source" in migration
    assert "resolution_satisfied" in migration
    assert "unique index clarifications_meal_stable_key_unique" in migration
