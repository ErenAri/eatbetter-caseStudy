from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.ai.schemas import CanonicalizationOutput
from app.application.services.meal_canonicalization_service import MealCanonicalizationService
from app.application.services.meal_review_service import MealReviewService
from app.domain.entities import CanonicalFoodCandidate, Meal, MealItem, PortionEstimate
from app.nutrition.normalization import canonical_gate_token_roles, normalize_food_query


def _meal_and_item(*, observed_name: str = "white rice") -> tuple[Meal, MealItem]:
    meal = Meal(
        user_id=UUID(int=1),
        meal_request_id=UUID(int=2),
        logged_at=datetime.now(timezone.utc),
    )
    item = MealItem(meal_id=meal.id, position=0, observed_name=observed_name)
    meal.items.append(item)
    return meal, item


def test_candidate_label_exposes_provenance_without_implying_validation() -> None:
    _meal, item = _meal_and_item()
    candidate = CanonicalFoodCandidate(
        meal_item_id=item.id,
        rank=1,
        source="USDA_FDC",
        source_food_id="123",
        name="Rice, white, cooked",
        data={"data_type": "Survey (FNDDS)"},
    )

    label = candidate.display_name()

    assert "FoodData Central · FNDDS" in label
    assert "USDA survey food" not in label


def test_canonical_clarification_always_has_manual_recovery_path() -> None:
    meal, item = _meal_and_item()
    item.candidates = [
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="USDA_FDC",
            source_food_id="123",
            name="Rice, white, cooked",
            data={"data_type": "Foundation"},
        )
    ]
    service = object.__new__(MealReviewService)

    service._ensure_identity(meal, item)

    clarification = meal.clarifications[-1]
    assert clarification.type == "CANONICAL_SELECTION"
    assert clarification.options[-1]["id"] == "manual-search"
    assert clarification.options[-1]["value"] == {"action": "MANUAL_SEARCH"}
    assert "best describes" in clarification.question


def test_portion_question_shows_numeric_estimates_instead_of_smaller_larger_anchor() -> None:
    meal, item = _meal_and_item()
    item.portion_estimate = PortionEstimate(Decimal("120"), Decimal("180"))
    service = object.__new__(MealReviewService)

    service._ensure_portion(meal, item, ())

    clarification = meal.clarifications[-1]
    assert [option["label"] for option in clarification.options] == [
        "About 120 g",
        "About 150 g",
        "About 180 g",
    ]
    assert clarification.question == "About how much white rice did you eat?"


def test_hidden_ingredient_question_is_explicitly_about_non_visible_use() -> None:
    meal, _item = _meal_and_item()
    service = object.__new__(MealReviewService)

    service._ensure_hidden(
        meal,
        {"name": "cooking oil", "potential_impact": "MATERIAL"},
    )

    assert meal.clarifications[-1].question == (
        "Was cooking oil used in a way the photo may not show?"
    )


def test_deterministic_gate_blocks_semantically_unrelated_model_selection() -> None:
    _meal, item = _meal_and_item(observed_name="white rice")
    item.preparation_method = "cooked"
    candidates = [
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="USDA_FDC",
            source_food_id="1",
            name="Beef, ground, cooked",
        ),
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=2,
            source="USDA_FDC",
            source_food_id="2",
            name="Rice, white, cooked",
        ),
    ]
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=1,
        match_quality="STRONG",
        reason_codes=["FOOD_IDENTITY_MATCH"],
    )

    assert not MealCanonicalizationService._selection_passes_deterministic_gate(
        item, candidates, output
    )


def test_deterministic_gate_allows_supported_selection() -> None:
    _meal, item = _meal_and_item(observed_name="white rice")
    item.preparation_method = "cooked"
    candidates = [
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="USDA_FDC",
            source_food_id="1",
            name="Rice, white, cooked",
        )
    ]
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=1,
        match_quality="STRONG",
        reason_codes=["FOOD_IDENTITY_MATCH", "PREPARATION_MATCH"],
    )

    assert MealCanonicalizationService._selection_passes_deterministic_gate(
        item, candidates, output
    )


def test_gate_roles_separate_plural_identity_preparation_and_form() -> None:
    identity, preparation = canonical_gate_token_roles("chopped scrambled eggs")

    assert identity == frozenset({"egg"})
    assert preparation == frozenset({"scrambled"})


def test_gate_plural_normalization_keeps_collective_food_nouns_conservative() -> None:
    identity, preparation = canonical_gate_token_roles("greens and couscous")

    assert "greens" in identity
    assert "green" not in identity
    assert "couscous" in identity
    assert preparation == frozenset()


def test_gate_specific_vocabulary_does_not_change_retrieval_normalization() -> None:
    # Retrieval remains intentionally unchanged until the retrieval-v2 PR.
    assert normalize_food_query("scrambled eggs") == "scrambled eggs"


def test_deterministic_gate_allows_supported_scrambled_egg_rank_two() -> None:
    _meal, item = _meal_and_item(observed_name="scrambled eggs")
    item.preparation_method = "scrambled"
    candidates = [
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="USDA_FDC",
            source_food_id="1",
            name="Eggs, scrambled, frozen mixture",
        ),
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=2,
            source="USDA_FDC",
            source_food_id="2707198",
            name="Egg omelet or scrambled egg, NS as to fat",
        ),
    ]
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=2,
        match_quality="EXACT",
        reason_codes=["FOOD_IDENTITY_MATCH", "PREPARATION_MATCH"],
    )

    assert MealCanonicalizationService._selection_passes_deterministic_gate(
        item, candidates, output
    )


def test_deterministic_gate_ignores_form_descriptor_for_identity_support() -> None:
    _meal, item = _meal_and_item(observed_name="chopped cooked chicken")
    item.preparation_method = "cooked"
    candidates = [
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="USDA_FDC",
            source_food_id="2705954",
            name="Chicken breast, cooked",
        )
    ]
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=1,
        match_quality="STRONG",
        reason_codes=["FOOD_IDENTITY_MATCH", "PREPARATION_MATCH"],
    )

    assert MealCanonicalizationService._selection_passes_deterministic_gate(
        item, candidates, output
    )


def test_deterministic_gate_still_blocks_preparation_mismatch() -> None:
    _meal, item = _meal_and_item(observed_name="fried eggs")
    item.preparation_method = "fried"
    candidates = [
        CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="USDA_FDC",
            source_food_id="1",
            name="Egg, boiled",
        )
    ]
    output = CanonicalizationOutput(
        decision="SELECT",
        selected_candidate_rank=1,
        match_quality="EXACT",
        reason_codes=["FOOD_IDENTITY_MATCH"],
    )

    assert not MealCanonicalizationService._selection_passes_deterministic_gate(
        item, candidates, output
    )
