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

# Canonical-selection safety needs a richer vocabulary than retrieval currently
# uses, but sharing that vocabulary with PREPARATION_TERMS would silently change
# retrieval/ranking behavior. Keep the gate representation isolated until the
# retrieval strategy is intentionally revised and re-evaluated.
CANONICAL_GATE_PREPARATION_TERMS = frozenset(
    set(PREPARATION_TERMS)
    | {
        "braised",
        "broiled",
        "poached",
        "sauteed",
        "scrambled",
        "smoked",
        "toasted",
    }
)

# Shape/form words can leak into model food names (for example
# "chopped cooked chicken") but should not become food-identity evidence.
CANONICAL_GATE_FORM_TERMS = frozenset(
    {
        "chopped",
        "crushed",
        "diced",
        "halved",
        "minced",
        "shredded",
        "sliced",
    }
)

_CANONICAL_GATE_PLURAL_EXCEPTIONS = frozenset(
    {
        "greens",  # collective food noun; "green" is not an equivalent identity
        "molasses",
    }
)


def normalize_food_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    descriptive = [token for token in tokens if token not in PREPARATION_TERMS]
    preparation = [token for token in tokens if token in PREPARATION_TERMS]
    return " ".join(descriptive + preparation)


def _canonical_gate_token(value: str) -> str:
    """Apply deliberately conservative food-domain plural normalization."""
    if value in _CANONICAL_GATE_PLURAL_EXCEPTIONS:
        return value
    if value.endswith("berries") and len(value) > len("berries"):
        return value[:-3] + "y"
    if value == "berries":
        return "berry"
    if value.endswith(("ches", "shes", "xes", "zes")) and len(value) > 4:
        return value[:-2]
    if value.endswith("oes") and len(value) > 4:
        return value[:-2]
    if (
        value.endswith("s")
        and len(value) > 3
        and not value.endswith(("ss", "us", "is", "ous"))
    ):
        return value[:-1]
    return value


def canonical_gate_token_roles(value: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return normalized identity and preparation tokens for the safety gate.

    This is intentionally narrower than stemming/lemmatization: it handles
    common food plurals, separates preparation terms, and drops non-identity
    form descriptors without changing the retrieval query representation.
    """
    decomposed = unicodedata.normalize("NFKD", value).lower()
    ascii_safe = "".join(character for character in decomposed if not unicodedata.combining(character))
    tokens = [_canonical_gate_token(token) for token in re.findall(r"[a-z0-9]+", ascii_safe)]
    identity = frozenset(
        token
        for token in tokens
        if token not in CANONICAL_GATE_PREPARATION_TERMS
        and token not in CANONICAL_GATE_FORM_TERMS
    )
    preparation = frozenset(
        token for token in tokens if token in CANONICAL_GATE_PREPARATION_TERMS
    )
    return identity, preparation


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
