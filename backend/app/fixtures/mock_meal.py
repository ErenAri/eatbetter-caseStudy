from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities import (
    CanonicalFoodCandidate,
    Clarification,
    Meal,
    MealItem,
    NutritionPer100g,
    PortionEstimate,
)
from app.domain.enums import MealStatus, PortionResolutionSource


def build_review_fixture(user_id: UUID) -> Meal:
    meal = Meal(
        user_id=user_id,
        meal_request_id=uuid4(),
        logged_at=datetime.now(timezone.utc),
        user_context="Chicken and rice bowl with broccoli; olive oil amount unknown.",
    )
    definitions = (
        ("chicken breast", "grilled", "fixture-chicken", "Chicken breast, grilled", (165, 31, 0, 3.6), (120, 170), 145),
        ("white rice", "cooked", "fixture-rice", "Rice, white, cooked", (130, 2.7, 28.2, 0.3), (140, 220), 180),
        ("broccoli", "steamed", "fixture-broccoli", "Broccoli, cooked", (35, 2.4, 7.2, 0.4), (70, 110), 90),
        ("olive oil", None, "fixture-oil", "Olive oil", (884, 0, 0, 100), (0, 27), None),
    )
    for position, definition in enumerate(definitions):
        observed, preparation, source_id, name, nutrition, portion_range, confirmed = definition
        item = MealItem(
            meal_id=meal.id,
            position=position,
            observed_name=observed,
            normalized_name=observed,
            preparation_method=preparation,
            portion_estimate=PortionEstimate(*portion_range),
            confirmed_portion_g=Decimal(str(confirmed)) if confirmed is not None else None,
            portion_resolution_source=(
                PortionResolutionSource.AUTO_ESTIMATE if confirmed is not None else None
            ),
            requires_clarification=observed == "olive oil",
            clarification_resolved=observed != "olive oil",
        )
        snapshot = NutritionPer100g(*nutrition)
        candidate = CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=1,
            source="TEST_DEMO_DATA",
            source_food_id=source_id,
            name=name,
            nutrition_per_100g=snapshot,
            data={"fixture": True, "data_type": "TEST/DEMO DATA — NOT USDA RESULTS"},
        )
        item.candidates.append(candidate)
        item.select_candidate(1)
        item.nutrition_snapshot = snapshot
        item.nutrition_retrieved_at = candidate.created_at
        item.recalculate()
        meal.items.append(item)

    oil = meal.items[-1]
    meal.clarifications.append(
        Clarification(
            meal_id=meal.id,
            meal_item_id=oil.id,
            type="PORTION",
            question="How much olive oil was used?",
            options=(
                {"id": "none", "label": "None", "value": {"grams": "0"}},
                {"id": "one-teaspoon", "label": "1 tsp", "value": {"grams": "4.5", "household_unit": "tsp"}},
                {"id": "one-tablespoon", "label": "1 tbsp", "value": {"grams": "13.5", "household_unit": "tbsp"}},
                {"id": "two-tablespoons", "label": "2 tbsp", "value": {"grams": "27", "household_unit": "tbsp"}},
            ),
            reason_codes=("ABSOLUTE_CALORIE_UNCERTAINTY",),
            stable_key=f"portion:{oil.id}",
        )
    )
    meal.transition_to(MealStatus.ANALYZING)
    meal.transition_to(MealStatus.NEEDS_REVIEW)
    return meal


def build_canonical_review_fixture(user_id: UUID) -> Meal:
    meal = Meal(
        user_id=user_id,
        meal_request_id=uuid4(),
        logged_at=datetime.now(timezone.utc),
        user_context="Deterministic canonical ambiguity demo.",
    )
    item = MealItem(
        meal_id=meal.id,
        position=0,
        observed_name="creamy sauce",
        normalized_name="creamy sauce",
        portion_estimate=PortionEstimate(Decimal("30"), Decimal("60")),
        observation_certainty="MEDIUM",
        requires_clarification=True,
    )
    for rank, source_id, name, nutrition in (
        (1, "fixture-cream-sauce", "Cream sauce", (190, 3, 8, 16)),
        (2, "fixture-cheese-sauce", "Cheese sauce", (174, 6, 9, 13)),
    ):
        item.candidates.append(CanonicalFoodCandidate(
            meal_item_id=item.id,
            rank=rank,
            source="TEST_DEMO_DATA",
            source_food_id=source_id,
            name=name,
            nutrition_per_100g=NutritionPer100g(*nutrition),
            data={"fixture": True, "data_type": "TEST/DEMO DATA — NOT USDA RESULTS"},
        ))
    meal.items.append(item)
    meal.clarifications.append(Clarification(
        meal_id=meal.id,
        meal_item_id=item.id,
        type="CANONICAL_SELECTION",
        question="Which food best matches creamy sauce?",
        options=tuple({"id": f"candidate-{value.rank}", "label": value.name, "value": {"candidate_rank": value.rank}} for value in item.candidates),
        reason_codes=("CANONICAL_AMBIGUOUS",),
        stable_key=f"canonical:{item.id}",
    ))
    meal.transition_to(MealStatus.ANALYZING)
    meal.transition_to(MealStatus.NEEDS_REVIEW)
    return meal
