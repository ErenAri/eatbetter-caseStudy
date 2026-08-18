import re
import unicodedata


PREPARATION_TERMS = frozenset(
    {
        "baked",
        "boiled",
        "cooked",
        "fried",
        "grilled",
        "raw",
        "roasted",
        "skinless",
        "steamed",
    }
)

SAFE_PREPARATION_PHRASES = (
    "with skin",
    "skinless",
    "baked",
    "boiled",
    "cooked",
    "fried",
    "grilled",
    "raw",
    "roasted",
    "steamed",
)

GROUNDING_QUERY_ALIASES = {
    # USDA reference datasets index the generic cooked noodle under pasta, not
    # the branded-heavy exact term returned by meal observation.
    "spaghetti": "pasta cooked",
    # The reference entry is indexed under the full commodity description.
    "tomato sauce": "tomato products canned sauce",
}


def normalize_food_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    descriptive = [token for token in tokens if token not in PREPARATION_TERMS]
    preparation = [token for token in tokens if token in PREPARATION_TERMS]
    return " ".join(descriptive + preparation)


def build_grounding_query(observed_name: str, preparation_method: str | None) -> str:
    base = normalize_food_query(observed_name)
    base = GROUNDING_QUERY_ALIASES.get(base, base)
    if not preparation_method:
        return base
    normalized_preparation = " ".join(
        re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", preparation_method).lower())
    )
    additions: list[str] = []
    base_tokens = set(base.split())
    for phrase in SAFE_PREPARATION_PHRASES:
        phrase_tokens = phrase.split()
        if phrase in normalized_preparation and not set(phrase_tokens).issubset(base_tokens):
            additions.extend(token for token in phrase_tokens if token not in base_tokens)
            base_tokens.update(phrase_tokens)
    return normalize_food_query(" ".join((base, *additions)))
