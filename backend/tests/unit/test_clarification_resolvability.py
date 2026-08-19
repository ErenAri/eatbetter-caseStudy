from decimal import Decimal
from uuid import UUID

from app.ai.schemas import CanonicalizationOutput
from app.application.services.meal_canonicalization_service import MealCanonicalizationService
from app.application.services.meal_review_service import MealReviewService
from app.domain.entities import CanonicalFoodCandidate, Meal, MealItem, PortionEstimate


def _meal_and_item(*, observed_name: str = "white rice") -> tuple[Meal, MealItem]:
    meal = Meal(user_id=UUID(int=1), meal_request_id=UUID(int=2))
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
