import json

import pytest
from pydantic import ValidationError

from app.ai.schemas import MealObservation, ObservedFood, PortionEstimateSchema


def valid_observation() -> dict:
    return {
        "image_quality": {"usable": True, "issues": []},
        "items": [
            {
                "observed_name": "white rice",
                "preparation_method": "cooked",
                "portion_estimate": {"min_g": 140, "max_g": 220},
                "observation_certainty": "MEDIUM",
                "alternatives": ["basmati rice", "jasmine rice"],
                "uncertainties": ["rice variety"],
                "visible_evidence": ["white cooked rice grains"],
            }
        ],
        "possible_hidden_ingredients": [
            {
                "name": "cooking oil",
                "reason": "amount is not visually measurable",
                "potential_impact": "MATERIAL",
            }
        ],
        "meal_level_uncertainties": ["exact quantities"],
    }


def test_strict_observation_supports_alternatives_and_hidden_ingredients() -> None:
    observation = MealObservation.model_validate(valid_observation())

    assert observation.items[0].alternatives == ["basmati rice", "jasmine rice"]
    assert observation.possible_hidden_ingredients[0].name == "cooking oil"
    assert "cooking oil" not in [item.observed_name for item in observation.items]


def test_unknown_portion_and_empty_food_list_are_valid() -> None:
    value = valid_observation()
    value["items"][0]["portion_estimate"] = None
    assert MealObservation.model_validate(value).items[0].portion_estimate is None

    value["items"] = []
    assert MealObservation.model_validate(value).items == []


def test_portion_range_and_sanity_bound_are_enforced() -> None:
    with pytest.raises(ValidationError):
        PortionEstimateSchema(min_g=200, max_g=100)
    with pytest.raises(ValidationError):
        PortionEstimateSchema(min_g=0, max_g=5001)


def test_unusable_and_non_meal_images_cannot_contain_foods() -> None:
    value = valid_observation()
    value["image_quality"] = {"usable": False, "issues": ["IMAGE_NOT_MEAL"]}
    value["items"] = []
    assert not MealObservation.model_validate(value).image_quality.usable

    value["items"] = valid_observation()["items"]
    with pytest.raises(ValidationError):
        MealObservation.model_validate(value)


@pytest.mark.parametrize("forbidden", ["calories", "protein", "carbs", "fat", "fdc_id", "usda_id"])
def test_nutrition_and_database_fields_are_rejected(forbidden: str) -> None:
    value = valid_observation()
    value["items"][0][forbidden] = 500
    with pytest.raises(ValidationError):
        MealObservation.model_validate(value)


def test_schema_contains_no_authoritative_nutrition_or_food_id_fields() -> None:
    schema = json.dumps(MealObservation.model_json_schema()).lower()
    for forbidden in ("calories", "protein", "carbs", "fat", "fdc_id", "usda_id"):
        assert forbidden not in schema


def test_alternatives_are_limited_to_three() -> None:
    with pytest.raises(ValidationError):
        ObservedFood.model_validate(
            {
                **valid_observation()["items"][0],
                "alternatives": ["a", "b", "c", "d"],
            }
        )
