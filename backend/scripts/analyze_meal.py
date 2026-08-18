"""Run P4-only OpenAI meal observation against a private local image."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.providers import OpenAIVisionProvider
from app.domain.entities import MealImage
from app.infrastructure.config import Settings


async def analyze(path: Path, context: str | None) -> int:
    settings = Settings.from_env()
    if settings.openai_api_key is None:
        raise SystemExit("OPENAI_API_KEY is not configured; no request was made.")
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is empty; no request was made.")
    mime_type = mimetypes.guess_type(path.name)[0] or ""
    try:
        image = MealImage(path.read_bytes(), mime_type)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Cannot analyze image: {error}") from None

    provider = OpenAIVisionProvider(
        api_key=api_key,
        model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort,
        image_detail=settings.openai_image_detail,
        timeout_seconds=settings.openai_timeout_seconds,
        max_attempts=settings.openai_max_attempts,
    )
    try:
        result = await provider.analyze_meal(
            image=image, user_context=context, request_id=uuid4()
        )
    finally:
        await provider.aclose()
    print(result.observation.model_dump_json(indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a meal image without USDA lookup.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--context", default=None)
    args = parser.parse_args()
    return asyncio.run(analyze(args.image, args.context))


if __name__ == "__main__":
    raise SystemExit(main())
