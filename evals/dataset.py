from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Split(StrEnum):
    DEVELOPMENT = "development"
    HOLDOUT = "holdout"


class Category(StrEnum):
    SIMPLE = "SIMPLE"
    MULTI_COMPONENT = "MULTI_COMPONENT"
    PORTION_SENSITIVE = "PORTION_SENSITIVE"
    SAUCE_OR_OIL = "SAUCE_OR_OIL"
    HIDDEN_INGREDIENT = "HIDDEN_INGREDIENT"
    COMPOSITE_FOOD = "COMPOSITE_FOOD"
    PACKAGED_FOOD = "PACKAGED_FOOD"
    TURKISH_LOCAL = "TURKISH_LOCAL"
    LOW_QUALITY_IMAGE = "LOW_QUALITY_IMAGE"
    NON_MEAL = "NON_MEAL"


class CanonicalGroundTruthStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNMAPPABLE = "UNMAPPABLE"
    UNVERIFIED = "UNVERIFIED"


class ConsentOrOwnership(StrEnum):
    OWNER_CAPTURED = "OWNER_CAPTURED"
    EXPLICIT_CONSENT = "EXPLICIT_CONSENT"
    LICENSED = "LICENSED"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NutritionTruth(StrictModel):
    calories_kcal: Decimal | None = Field(default=None, ge=0)
    protein_g: Decimal | None = Field(default=None, ge=0)
    carbs_g: Decimal | None = Field(default=None, ge=0)
    fat_g: Decimal | None = Field(default=None, ge=0)
    measurement_method: str = Field(min_length=1, max_length=500)


class GroundTruthItem(StrictModel):
    item_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=200)
    acceptable_aliases: list[str] = Field(default_factory=list, max_length=20)
    preparation: str | None = Field(default=None, max_length=100)
    portion_truth_g: Decimal | None = Field(default=None, ge=0)
    expected_fdc_id: str | None = None
    expected_fdc_name: str | None = Field(default=None, max_length=300)
    acceptable_fdc_ids: list[str] = Field(default_factory=list, max_length=10)
    canonical_ground_truth_status: CanonicalGroundTruthStatus = (
        CanonicalGroundTruthStatus.UNVERIFIED
    )
    notes: str = Field(default="", max_length=1000)

    @field_validator("expected_fdc_id")
    @classmethod
    def valid_optional_fdc_id(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError("FDC IDs must be positive integer strings")
        return value

    @field_validator("acceptable_fdc_ids")
    @classmethod
    def valid_fdc_ids(cls, values: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[1-9][0-9]*", value) for value in values):
            raise ValueError("FDC IDs must be positive integer strings")
        if len(values) != len(set(values)):
            raise ValueError("acceptable_fdc_ids cannot contain duplicates")
        return values

    @model_validator(mode="after")
    def consistent_canonical_truth(self) -> "GroundTruthItem":
        supplied = set(self.acceptable_fdc_ids)
        if self.expected_fdc_id:
            supplied.add(self.expected_fdc_id)
        if self.canonical_ground_truth_status == CanonicalGroundTruthStatus.VERIFIED:
            if not self.expected_fdc_id or not self.expected_fdc_name:
                raise ValueError("VERIFIED items require expected_fdc_id and expected_fdc_name")
        elif self.canonical_ground_truth_status == CanonicalGroundTruthStatus.UNMAPPABLE:
            if supplied or self.expected_fdc_name:
                raise ValueError("UNMAPPABLE items cannot declare an FDC ground truth")
        return self

    @property
    def acceptable_canonical_ids(self) -> set[str]:
        return ({self.expected_fdc_id} if self.expected_fdc_id else set()) | set(
            self.acceptable_fdc_ids
        )


class HiddenIngredientTruth(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    present: bool
    portion_truth_g: Decimal | None = Field(default=None, ge=0)
    measurement_method: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def measured_values_have_method(self) -> "HiddenIngredientTruth":
        if self.portion_truth_g is not None and not self.measurement_method:
            raise ValueError("measured hidden ingredients require measurement_method")
        return self


class Provenance(StrictModel):
    captured_by: str = Field(min_length=1, max_length=100)
    capture_device: str | None = Field(default=None, max_length=200)
    capture_date: date
    ground_truth_method: str = Field(min_length=1, max_length=1000)
    consent_or_ownership: ConsentOrOwnership


class EvaluationCase(StrictModel):
    case_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    split: Split
    categories: list[Category] = Field(min_length=1)
    image: str = Field(min_length=1, max_length=500)
    items: list[GroundTruthItem] = Field(default_factory=list, max_length=30)
    hidden_ingredients: list[HiddenIngredientTruth] = Field(default_factory=list)
    nutrition_truth: NutritionTruth | None = None
    provenance: Provenance
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def valid_case(self) -> "EvaluationCase":
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("duplicate item_id in case")
        if len(self.categories) != len(set(self.categories)):
            raise ValueError("duplicate category in case")
        if Category.NON_MEAL in self.categories and self.items:
            raise ValueError("NON_MEAL cases cannot contain food items")
        path = Path(self.image)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("image must be a safe path relative to the manifest")
        return self


class DatasetManifest(StrictModel):
    schema_version: int = Field(ge=1)
    dataset_version: str = Field(min_length=1, max_length=100)
    cases: list[EvaluationCase]

    @model_validator(mode="after")
    def unique_cases(self) -> "DatasetManifest":
        seen: dict[str, Split] = {}
        for case in self.cases:
            prior = seen.get(case.case_id)
            if prior is not None:
                if prior != case.split:
                    raise ValueError(
                        f"case_id {case.case_id!r} appears in both development and holdout"
                    )
                raise ValueError(f"duplicate case_id {case.case_id!r}")
            seen[case.case_id] = case.split
        return self


def load_manifest(path: str | Path, *, require_images: bool = True) -> DatasetManifest:
    manifest_path = Path(path).resolve()
    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if require_images:
        for case in manifest.cases:
            image_path = (manifest_path.parent / case.image).resolve()
            if manifest_path.parent not in image_path.parents or not image_path.is_file():
                raise ValueError(f"missing image for {case.case_id}: {case.image}")
    return manifest


def decimal_json(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def schema_json() -> str:
    return json.dumps(DatasetManifest.model_json_schema(), indent=2, sort_keys=True)
