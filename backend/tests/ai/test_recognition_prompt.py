import hashlib
from pathlib import Path

from app.ai.providers import openai_vision

PROMPTS_DIR = Path(__file__).parents[2] / "app" / "ai" / "prompts"
V2_PATH = PROMPTS_DIR / "meal_recognition_v2.md"
V4_PATH = PROMPTS_DIR / "meal_recognition_v4.md"

# Mirrors vision_configuration.prompt_source_sha256 in
# evals/private/snapme/subset_v1/recognition_configuration_lock.json. meal_recognition_v2.md
# must stay byte-identical to what that eval was locked and measured against, so if this
# assertion fails, the prompt file was edited and should be reverted -- do not "fix" this by
# updating the constant to match the new file.
V2_FROZEN_SHA256 = "252885239b2cac2f307c42b2da6e216abd042721b3aafaa3493b14f3bdb50849"


def test_v4_drops_database_search_constraint() -> None:
    assert "suitable for database search" not in V4_PATH.read_text(encoding="utf-8")


def test_v4_names_dishes_by_common_name() -> None:
    assert "common dish name" in V4_PATH.read_text(encoding="utf-8")


def test_v2_still_constrains_names_for_database_search() -> None:
    assert "suitable for database search" in V2_PATH.read_text(encoding="utf-8")


def test_v2_prompt_bytes_are_unchanged() -> None:
    digest = hashlib.sha256(V2_PATH.read_bytes()).hexdigest()
    assert digest == V2_FROZEN_SHA256


def test_provider_points_at_v4() -> None:
    assert openai_vision.PROMPT_VERSION == "meal_recognition_v4"
    assert openai_vision.PROMPT_PATH.exists()
