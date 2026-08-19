from decimal import Decimal
from typing import Any

from .normalization import canonical_gate_token_roles, normalize_food_query


DATA_TYPE_BONUS = {
    "survey (fndds)": Decimal("30"),
    "foundation": Decimal("25"),
    "sr legacy": Decimal("20"),
    "branded": Decimal("-20"),
}

USDA_ADMINISTRATIVE_IDENTITY_TERMS = frozenset(
    {
        "added",
        "fat",
        "form",
        "ingredient",
        "method",
        "nfs",
        "ns",
        "type",
    }
)


def deterministic_food_score(query: str, food: Any) -> Decimal:
    """Retain USDA score/data-type evidence as a late deterministic tie-breaker."""
    normalized_query = normalize_food_query(query)
    normalized_description = normalize_food_query(food.description)
    query_tokens = set(normalized_query.split())
    description_tokens = set(normalized_description.split())
    overlap = len(query_tokens & description_tokens) / max(len(query_tokens), 1)
    score = Decimal(str(food.score or 0))
    score += Decimal(str(overlap)) * Decimal("20")
    if normalized_query == normalized_description:
        score += Decimal("40")
    score += DATA_TYPE_BONUS.get(food.data_type.lower(), Decimal("0"))
    if food.brand_owner:
        score -= Decimal("10")
    return score


def _preparation_support(
    query_preparation: frozenset[str], description_preparation: frozenset[str]
) -> int:
    if not query_preparation:
        return 1
    # "cooked" is an umbrella observation. A visible photo often cannot
    # distinguish baked/grilled/broiled/steamed with enough certainty to make
    # those narrower USDA descriptions a mismatch.
    if query_preparation == frozenset({"cooked"}):
        return int(bool(description_preparation) and "raw" not in description_preparation)
    return int(query_preparation.issubset(description_preparation))


def _normalized_description(value: str) -> str:
    return " ".join(value.lower().replace(",", " ").split())


def _generic_marker(description: str) -> int:
    lowered = _normalized_description(description)
    return int(" nfs" in f" {lowered}" or "ns as to" in lowered)


def _administrative_identity_terms(description: str) -> frozenset[str]:
    terms = set(USDA_ADMINISTRATIVE_IDENTITY_TERMS)
    lowered = _normalized_description(description)
    # In FoodData Central, "NS as to type of meat" describes uncertainty about
    # the subtype; "meat" is metadata wording rather than an added food identity.
    if "ns as to type of meat" in lowered:
        terms.add("meat")
    return frozenset(terms)


def _semantic_rank_key(query: str, food: Any) -> tuple:
    query_identity, query_preparation = canonical_gate_token_roles(query)
    description_identity, description_preparation = canonical_gate_token_roles(
        food.description
    )
    identity_support = len(query_identity & description_identity) / max(
        len(query_identity), 1
    )
    extra_identity = (
        description_identity
        - query_identity
        - _administrative_identity_terms(food.description)
    )
    # NFS/NS entries are useful generic defaults only when the candidate has not
    # changed food identity. For example, "Olives, NFS" is a good generic match
    # for "olives", but "Almond milk, NFS" must not get a genericity advantage
    # for an "almonds" observation merely because it contains the almond token.
    generic_suitability = _generic_marker(food.description) if not extra_identity else 0
    return (
        -identity_support,
        -_preparation_support(query_preparation, description_preparation),
        len(extra_identity),
        -generic_suitability,
        -deterministic_food_score(query, food),
        str(food.fdc_id),
    )


def rank_foods(query: str, foods: list[Any]) -> list[Any]:
    """Prefer semantic/generic compatibility before USDA's own text score.

    A broad visual observation should not be displaced by a narrower subtype
    merely because USDA's search engine scored that subtype higher. The original
    USDA score and data-type preference remain deterministic tie-breakers.
    """
    return sorted(foods, key=lambda food: _semantic_rank_key(query, food))
