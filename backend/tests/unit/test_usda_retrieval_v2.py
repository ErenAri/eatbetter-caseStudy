from types import SimpleNamespace

from app.nutrition.normalization import build_usda_query_variants
from app.nutrition.ranking import rank_foods


def food(fdc_id: int, description: str, *, data_type: str = "Survey (FNDDS)", score: float = 1):
    return SimpleNamespace(
        fdc_id=fdc_id,
        description=description,
        data_type=data_type,
        brand_owner=None,
        score=score,
    )


def test_usda_query_variants_require_identity_but_leave_preparation_optional() -> None:
    assert build_usda_query_variants("chopped cooked chicken") == (
        "+chicken cooked",
        "chopped chicken cooked",
    )
    assert build_usda_query_variants("scrambled eggs") == (
        "+egg scrambled",
        "scrambled eggs",
    )


def test_generic_nfs_food_outranks_narrower_composite_for_broad_observation() -> None:
    ranked = rank_foods(
        "olives",
        [
            food(1, "Olive tapenade", score=100),
            food(2, "Olives, NFS", score=1),
        ],
    )

    assert [value.fdc_id for value in ranked] == [2, 1]


def test_generic_ns_entry_outranks_unrequested_subtype() -> None:
    ranked = rank_foods(
        "bacon cooked",
        [
            food(1, "Beef, bacon, cooked", score=100),
            food(2, "Bacon, NS as to type of meat, cooked", score=1),
        ],
    )

    assert [value.fdc_id for value in ranked] == [2, 1]


def test_cooked_observation_accepts_narrower_cooked_method_but_not_raw() -> None:
    ranked = rank_foods(
        "salmon cooked",
        [
            food(1, "Fish, salmon, raw", score=100),
            food(2, "Fish, salmon, baked or broiled", score=1),
        ],
    )

    assert [value.fdc_id for value in ranked] == [2, 1]


def test_ns_brown_rice_outranks_as_ingredient_when_identity_is_equal() -> None:
    ranked = rank_foods(
        "brown rice cooked",
        [
            food(1, "Rice, brown, cooked, as ingredient", score=100),
            food(2, "Rice, brown, cooked, NS as to fat", score=1),
        ],
    )

    assert [value.fdc_id for value in ranked] == [2, 1]
