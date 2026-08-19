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
# uses. Retrieval v2 reuses the role classification, but not the gate thresholds.
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

# Function words are not food identity. Keeping them in the query denominator
# can create false abstentions for names such as "rice and beans".
CANONICAL_GATE_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "of",
        "or",
        "the",
        "to",
        "with",
        "without",
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


def canonical_gate_ordered_token_roles(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return de-duplicated identity/preparation tokens while preserving order."""
    decomposed = unicodedata.normalize("NFKD", value).lower()
    ascii_safe = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    identity: list[str] = []
    preparation: list[str] = []
    for raw_token in re.findall(r"[a-z0-9]+", ascii_safe):
        token = _canonical_gate_token(raw_token)
        if token in CANONICAL_GATE_PREPARATION_TERMS:
            if token not in preparation:
                preparation.append(token)
            continue
        if token in CANONICAL_GATE_FORM_TERMS or token in CANONICAL_GATE_STOPWORDS:
            continue
        if token not in identity:
            identity.append(token)
    return tuple(identity), tuple(preparation)


def canonical_gate_token_roles(value: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return normalized identity and preparation tokens for the safety gate.

    This is intentionally narrower than stemming/lemmatization: it handles
    common food plurals, separates preparation terms, and drops non-identity
    form descriptors/function words without changing the loose retrieval text.
    """
    identity, preparation = canonical_gate_ordered_token_roles(value)
    return frozenset(identity), frozenset(preparation)


def build_usda_query_variants(value: str) -> tuple[str, ...]:
    """Build a required-identity USDA query with a bounded loose fallback.

    FoodData Central treats plain terms broadly. Prefixing identity tokens with
    ``+`` makes them required while preparation remains optional evidence. The
    loose normalized query is retained as a fallback for analyzer/plural edge
    cases. Operators are intentionally introduced after generic normalization so
    provider code must not normalize them away again.
    """
    loose = normalize_food_query(value)
    identity, preparation = canonical_gate_ordered_token_roles(value)
    strict = " ".join(
        [*(f"+{token}" for token in identity), *preparation]
    ).strip()
    variants: list[str] = []
    for candidate in (strict, loose):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return tuple(variants)


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
