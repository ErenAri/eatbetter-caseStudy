from decimal import Decimal
from typing import Any

from .normalization import PREPARATION_TERMS, normalize_food_query


DATA_TYPE_BONUS = {
    "survey (fndds)": Decimal("30"),
    "foundation": Decimal("25"),
    "sr legacy": Decimal("20"),
    "branded": Decimal("-20"),
}


def deterministic_food_score(query: str, food: Any) -> Decimal:
    normalized_query = normalize_food_query(query)
    normalized_description = normalize_food_query(food.description)
    query_tokens = set(normalized_query.split())
    description_tokens = set(normalized_description.split())
    overlap = len(query_tokens & description_tokens) / max(len(query_tokens), 1)
    preparation_overlap = len(
        (query_tokens & PREPARATION_TERMS) & (description_tokens & PREPARATION_TERMS)
    )
    score = Decimal(str(food.score or 0))
    score += Decimal(str(overlap)) * Decimal("20")
    score += Decimal(preparation_overlap) * Decimal("8")
    if normalized_query == normalized_description:
        score += Decimal("40")
    score += DATA_TYPE_BONUS.get(food.data_type.lower(), Decimal("0"))
    if food.brand_owner:
        score -= Decimal("10")
    return score


def rank_foods(query: str, foods: list[Any]) -> list[Any]:
    return sorted(
        foods,
        key=lambda food: (
            -deterministic_food_score(query, food),
            str(food.fdc_id),
        ),
    )
