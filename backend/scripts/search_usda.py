"""Safely inspect USDA candidates without adding a development HTTP endpoint."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.config import Settings
from app.nutrition.providers import USDAFoodDataCentralProvider


def format_number(value: object) -> str:
    return "—" if value is None else str(value)


async def search(query: str, limit: int) -> int:
    settings = Settings.from_env()
    if settings.usda_api_key is None:
        raise SystemExit("USDA_API_KEY is not configured; no request was made.")
    api_key = settings.usda_api_key.get_secret_value()
    if not api_key or api_key.upper() == "DEMO_KEY":
        raise SystemExit("Configure a real USDA_API_KEY; DEMO_KEY is intentionally rejected.")

    provider = USDAFoodDataCentralProvider(
        api_key=api_key,
        base_url=settings.usda_base_url,
        timeout_seconds=settings.usda_timeout_seconds,
        search_pool_size=settings.usda_search_limit,
        max_attempts=settings.usda_max_attempts,
    )
    try:
        candidates = await provider.search_foods(query, meal_item_id=uuid4(), limit=limit)
    finally:
        await provider.aclose()

    print("rank\tFDC ID\tdescription\tdata type\tkcal/100g\tprotein g\tcarbs g\tfat g")
    for candidate in candidates:
        nutrition = candidate.nutrition_per_100g
        data = candidate.data or {}
        values = (
            candidate.rank,
            candidate.source_food_id,
            candidate.name.replace("\t", " "),
            data.get("data_type"),
            nutrition.calories_kcal if nutrition else None,
            nutrition.protein_g if nutrition else None,
            nutrition.carbs_g if nutrition else None,
            nutrition.fat_g if nutrition else None,
        )
        print("\t".join(format_number(value) for value in values))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Search USDA FoodData Central.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 21))
    args = parser.parse_args()
    return asyncio.run(search(args.query, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
