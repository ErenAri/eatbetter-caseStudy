from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from app.ai.schemas import MealObservation
from app.domain.entities import MealImage, VisionAnalysisResult


SCHEMA_VERSION = 1
FROZEN_PROVIDER_NAME = "FROZEN_RECOGNITION"


@dataclass(frozen=True, slots=True)
class VisionConfiguration:
    provider: str
    model: str
    prompt_version: str
    image_detail: str
    reasoning_effort: str


@dataclass(frozen=True, slots=True)
class RecognitionFixtureCase:
    case_id: str
    image_sha256: str
    observation: MealObservation


@dataclass(frozen=True, slots=True)
class RecognitionFixture:
    schema_version: int
    dataset_version: str
    split: str
    vision_configuration: VisionConfiguration
    cases: tuple[RecognitionFixtureCase, ...]
    content_sha256: str


class FrozenVisionProvider:
    provider_name = FROZEN_PROVIDER_NAME

    def __init__(self, fixture: RecognitionFixture) -> None:
        self.model = fixture.vision_configuration.model
        self.prompt_version = fixture.vision_configuration.prompt_version
        self.image_detail = fixture.vision_configuration.image_detail
        self.reasoning_effort = fixture.vision_configuration.reasoning_effort
        self._by_image_sha256 = {case.image_sha256: case for case in fixture.cases}

    async def analyze_meal(
        self,
        *,
        image: MealImage,
        user_context: str | None,
        request_id: UUID | None = None,
    ) -> VisionAnalysisResult:
        del user_context, request_id
        digest = sha256(image.content).hexdigest()
        frozen = self._by_image_sha256.get(digest)
        if frozen is None:
            raise ValueError(
                "meal image is not present in the frozen recognition fixture"
            )
        return VisionAnalysisResult(
            observation=frozen.observation,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            image_detail=self.image_detail,
            reasoning_effort=self.reasoning_effort,
            input_tokens=None,
            output_tokens=None,
            retry_count=0,
        )

    async def aclose(self) -> None:
        return None


def manifest_image_hashes(manifest_path: Path, cases: list[Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    seen_hashes: set[str] = set()
    for case in cases:
        image_path = (manifest_path.parent / case.image).resolve()
        digest = sha256(image_path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            raise ValueError(
                "frozen recognition requires unique image bytes per evaluation case"
            )
        seen_hashes.add(digest)
        output[case.case_id] = digest
    return output


def write_recognition_fixture(
    path: Path,
    *,
    dataset_version: str,
    split: str,
    vision_configuration: VisionConfiguration,
    expected_case_ids: list[str],
    records: list[dict],
) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite recognition fixture: {path}")
    by_id = {record.get("case_id"): record for record in records}
    if len(by_id) != len(records):
        raise ValueError("recognition fixture contains duplicate case ids")
    if set(by_id) != set(expected_case_ids):
        raise ValueError("recognition fixture case ids do not match the requested split")

    cases = []
    image_hashes: set[str] = set()
    for case_id in expected_case_ids:
        record = by_id[case_id]
        if record.get("status") != "completed":
            raise ValueError(
                "recognition fixture can only be written when every requested case completed"
            )
        image_sha256 = str(record.get("image_sha256") or "")
        if len(image_sha256) != 64:
            raise ValueError("recognition fixture record is missing image SHA-256")
        if image_sha256 in image_hashes:
            raise ValueError("recognition fixture image hashes must be unique")
        image_hashes.add(image_sha256)
        observation = MealObservation.model_validate(record.get("observation"))
        cases.append(
            {
                "case_id": case_id,
                "image_sha256": image_sha256,
                "observation": observation.model_dump(mode="json"),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "split": split,
        "vision_configuration": {
            "provider": vision_configuration.provider,
            "model": vision_configuration.model,
            "prompt_version": vision_configuration.prompt_version,
            "image_detail": vision_configuration.image_detail,
            "reasoning_effort": vision_configuration.reasoning_effort,
        },
        "cases": cases,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def load_recognition_fixture(
    path: Path,
    *,
    dataset_version: str,
    split: str,
    expected_images: dict[str, str],
) -> RecognitionFixture:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported recognition fixture schema version")
    if payload.get("dataset_version") != dataset_version:
        raise ValueError("recognition fixture dataset version does not match manifest")
    if payload.get("split") != split:
        raise ValueError("recognition fixture split does not match benchmark split")

    configuration = payload.get("vision_configuration")
    if not isinstance(configuration, dict):
        raise ValueError("recognition fixture is missing vision configuration")
    vision_configuration = VisionConfiguration(
        provider=_required_text(configuration, "provider"),
        model=_required_text(configuration, "model"),
        prompt_version=_required_text(configuration, "prompt_version"),
        image_detail=_required_text(configuration, "image_detail"),
        reasoning_effort=_required_text(configuration, "reasoning_effort"),
    )

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("recognition fixture cases must be a list")
    cases: list[RecognitionFixtureCase] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("recognition fixture case must be an object")
        case_id = _required_text(raw_case, "case_id")
        image_sha256 = _required_text(raw_case, "image_sha256")
        if case_id in seen_ids:
            raise ValueError("recognition fixture contains duplicate case ids")
        if image_sha256 in seen_hashes:
            raise ValueError("recognition fixture contains duplicate image hashes")
        seen_ids.add(case_id)
        seen_hashes.add(image_sha256)
        cases.append(
            RecognitionFixtureCase(
                case_id=case_id,
                image_sha256=image_sha256,
                observation=MealObservation.model_validate(raw_case.get("observation")),
            )
        )

    if seen_ids != set(expected_images):
        raise ValueError("recognition fixture case ids do not match the requested split")
    for case in cases:
        if expected_images[case.case_id] != case.image_sha256:
            raise ValueError(
                f"recognition fixture image hash does not match manifest for {case.case_id}"
            )

    return RecognitionFixture(
        schema_version=SCHEMA_VERSION,
        dataset_version=dataset_version,
        split=split,
        vision_configuration=vision_configuration,
        cases=tuple(cases),
        content_sha256=sha256(raw).hexdigest(),
    )


def _required_text(value: dict, key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"recognition fixture field {key} must be non-empty text")
    return result.strip()
