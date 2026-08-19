from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EquivalenceDecision(StrEnum):
    EQUIVALENT = "EQUIVALENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    UNCERTAIN = "UNCERTAIN"


class NutritionSnapshot(StrictModel):
    calories_kcal: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)


class FoodSnapshot(StrictModel):
    fdc_id: str
    name: str = Field(min_length=1, max_length=300)
    data_type: str | None = Field(default=None, max_length=100)
    nutrition_per_100g: NutritionSnapshot | None = None

    @field_validator("fdc_id")
    @classmethod
    def valid_fdc_id(cls, value: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError("FDC IDs must be positive integer strings")
        return value


class BlindedReviewPair(StrictModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_label: str = Field(min_length=1, max_length=200)
    target_preparation: str | None = Field(default=None, max_length=100)
    food_a: FoodSnapshot
    food_b: FoodSnapshot

    @model_validator(mode="after")
    def distinct_foods(self) -> "BlindedReviewPair":
        if self.food_a.fdc_id == self.food_b.fdc_id:
            raise ValueError("equivalence pair must contain two distinct FDC IDs")
        return self


class EquivalenceReviewPacket(StrictModel):
    schema_version: int = Field(default=1, ge=1)
    dataset_version: str = Field(min_length=1, max_length=100)
    split: str = Field(pattern=r"^development$")
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_candidate_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_utc: str
    blindness_note: str = Field(min_length=1, max_length=1000)
    pairs: list[BlindedReviewPair]

    @model_validator(mode="after")
    def unique_pairs(self) -> "EquivalenceReviewPacket":
        ids = [pair.pair_id for pair in self.pairs]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate pair_id in equivalence review packet")
        return self


class ReviewKeyEntry(StrictModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_id: str = Field(min_length=1, max_length=100)
    item_id: str = Field(min_length=1, max_length=100)
    reference_fdc_id: str
    candidate_fdc_id: str

    @field_validator("reference_fdc_id", "candidate_fdc_id")
    @classmethod
    def valid_fdc_id(cls, value: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError("FDC IDs must be positive integer strings")
        return value


class EquivalenceReviewKey(StrictModel):
    schema_version: int = Field(default=1, ge=1)
    dataset_version: str = Field(min_length=1, max_length=100)
    split: str = Field(pattern=r"^development$")
    review_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_candidate_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    warning: str = Field(min_length=1, max_length=500)
    entries: list[ReviewKeyEntry]

    @model_validator(mode="after")
    def unique_pairs(self) -> "EquivalenceReviewKey":
        ids = [entry.pair_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate pair_id in equivalence review key")
        return self


class EquivalenceAdjudication(StrictModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: EquivalenceDecision
    rationale: str = Field(min_length=5, max_length=1000)


class EquivalenceAdjudicationSet(StrictModel):
    schema_version: int = Field(default=1, ge=1)
    dataset_version: str = Field(min_length=1, max_length=100)
    split: str = Field(pattern=r"^development$")
    review_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str = Field(min_length=1, max_length=200)
    reviewed_utc: str
    adjudications: list[EquivalenceAdjudication]

    @field_validator("reviewer")
    @classmethod
    def completed_reviewer(cls, value: str) -> str:
        if value.upper().startswith("REPLACE"):
            raise ValueError("reviewer placeholder must be replaced before scoring")
        return value

    @field_validator("reviewed_utc")
    @classmethod
    def valid_reviewed_utc(cls, value: str) -> str:
        if value.upper().startswith("REPLACE"):
            raise ValueError("reviewed_utc placeholder must be replaced before scoring")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("reviewed_utc must be an ISO-8601 timestamp") from None
        if parsed.tzinfo is None:
            raise ValueError("reviewed_utc must include a timezone")
        return value

    @model_validator(mode="after")
    def unique_pairs(self) -> "EquivalenceAdjudicationSet":
        ids = [entry.pair_id for entry in self.adjudications]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate pair_id in equivalence adjudication set")
        return self


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: BaseModel | dict | list) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def stable_pair_id(
    *,
    dataset_version: str,
    case_id: str,
    item_id: str,
    reference_fdc_id: str,
    candidate_fdc_id: str,
) -> str:
    payload = "\x1f".join(
        (
            dataset_version,
            case_id,
            item_id,
            reference_fdc_id,
            candidate_fdc_id,
        )
    ).encode("utf-8")
    return sha256_bytes(payload)


def reference_goes_first(pair_id: str) -> bool:
    """Deterministically blind reference/candidate role without RNG state."""
    return int(pair_id[:2], 16) % 2 == 0


def write_immutable_json(path: str | Path, value: BaseModel | dict | list) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(value)
    with output.open("xb") as stream:
        stream.write(data)
    return sha256_bytes(data)


def load_review_packet(path: str | Path) -> EquivalenceReviewPacket:
    return EquivalenceReviewPacket.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_review_key(path: str | Path) -> EquivalenceReviewKey:
    return EquivalenceReviewKey.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_adjudications(path: str | Path) -> EquivalenceAdjudicationSet:
    return EquivalenceAdjudicationSet.model_validate_json(Path(path).read_text(encoding="utf-8"))


def validate_adjudications(
    *,
    packet: EquivalenceReviewPacket,
    packet_sha256: str,
    key: EquivalenceReviewKey,
    adjudications: EquivalenceAdjudicationSet,
) -> None:
    packet_ids = {pair.pair_id for pair in packet.pairs}
    key_ids = {entry.pair_id for entry in key.entries}
    adjudicated_ids = {entry.pair_id for entry in adjudications.adjudications}
    if packet_sha256 != key.review_packet_sha256:
        raise ValueError("review key does not belong to this review packet")
    if packet_sha256 != adjudications.review_packet_sha256:
        raise ValueError("adjudications do not belong to this review packet")
    if packet.dataset_version != key.dataset_version or packet.dataset_version != adjudications.dataset_version:
        raise ValueError("dataset version differs across equivalence artifacts")
    if packet.split != key.split or packet.split != adjudications.split:
        raise ValueError("split differs across equivalence artifacts")
    if packet_ids != key_ids:
        raise ValueError("review key pair set differs from review packet")
    if packet_ids != adjudicated_ids:
        missing = sorted(packet_ids - adjudicated_ids)
        extra = sorted(adjudicated_ids - packet_ids)
        raise ValueError(f"adjudication pair set mismatch; missing={missing}, extra={extra}")


def equivalent_candidate_ids_by_item(
    key: EquivalenceReviewKey,
    adjudications: EquivalenceAdjudicationSet,
) -> dict[tuple[str, str], set[str]]:
    decisions = {entry.pair_id: entry.decision for entry in adjudications.adjudications}
    output: dict[tuple[str, str], set[str]] = {}
    for entry in key.entries:
        if decisions.get(entry.pair_id) != EquivalenceDecision.EQUIVALENT:
            continue
        output.setdefault((entry.case_id, entry.item_id), set()).add(entry.candidate_fdc_id)
    return output


def nutrition_snapshot(canonical_food: Any | None) -> NutritionSnapshot | None:
    if canonical_food is None or canonical_food.nutrition_per_100g is None:
        return None
    value = canonical_food.nutrition_per_100g
    return NutritionSnapshot(
        calories_kcal=float(value.calories_kcal) if value.calories_kcal is not None else None,
        protein_g=float(value.protein_g) if value.protein_g is not None else None,
        carbs_g=float(value.carbs_g) if value.carbs_g is not None else None,
        fat_g=float(value.fat_g) if value.fat_g is not None else None,
    )


def food_snapshot(canonical_food: Any) -> FoodSnapshot:
    data = canonical_food.data if isinstance(canonical_food.data, dict) else {}
    return FoodSnapshot(
        fdc_id=str(canonical_food.source_food_id),
        name=str(canonical_food.name),
        data_type=str(data.get("data_type")) if data.get("data_type") is not None else None,
        nutrition_per_100g=nutrition_snapshot(canonical_food),
    )
