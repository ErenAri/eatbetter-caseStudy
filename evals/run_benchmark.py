from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.infrastructure.config import Settings
from evals.configuration import ConfigurationName, snapshot, validate_real_providers
from evals.dataset import Split, load_manifest
from evals.live_benchmark import run_live
from evals.recognition_fixture import load_recognition_fixture, manifest_image_hashes
from evals.reporting import write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P8 real-provider meal benchmark.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--frozen-configuration", type=Path, help="Required for holdout; created before holdout inspection.")
    parser.add_argument("--write-final-configuration", type=Path, help="Write the chosen development configuration once.")
    parser.add_argument(
        "--frozen-recognition",
        type=Path,
        help=(
            "Development-only: replay an immutable recognition fixture instead of calling vision. "
            "Use this for downstream retrieval/selector ablations on identical upstream observations."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    selected = [case for case in manifest.cases if str(case.split) == args.split]
    if not selected:
        raise SystemExit(f"manifest has no {args.split} cases")
    # The documented command runs from the repository root while server secrets live in backend/.env.
    # Process environment values still override this local file through pydantic-settings.
    settings = Settings(_env_file=ROOT / "backend" / ".env")
    validate_real_providers(settings)

    recognition_fixture = None
    if args.frozen_recognition:
        if args.split != str(Split.DEVELOPMENT):
            raise SystemExit("frozen recognition replay is development-only to protect holdout isolation")
        recognition_fixture = load_recognition_fixture(
            args.frozen_recognition.resolve(),
            dataset_version=manifest.dataset_version,
            split=args.split,
            expected_images=manifest_image_hashes(manifest_path, selected),
        )

    frozen_vision_configuration = None
    if recognition_fixture is not None:
        source = recognition_fixture.vision_configuration
        frozen_vision_configuration = {
            "provider": source.provider,
            "model": source.model,
            "prompt_version": source.prompt_version,
            "image_detail": source.image_detail,
            "reasoning_effort": source.reasoning_effort,
        }
    snapshots = [
        snapshot(
            settings,
            configuration=name,
            dataset_version=manifest.dataset_version,
            split=args.split,
            seed=args.seed,
            recognition_input_mode="FROZEN" if recognition_fixture else "LIVE",
            recognition_fixture_sha256=(
                recognition_fixture.content_sha256 if recognition_fixture else None
            ),
            frozen_vision_configuration=frozen_vision_configuration,
        )
        for name in ConfigurationName
    ]

    if args.split == str(Split.HOLDOUT):
        if not args.frozen_configuration or not args.frozen_configuration.is_file():
            raise SystemExit("holdout requires --frozen-configuration written before the holdout run")
        frozen = json.loads(args.frozen_configuration.read_text(encoding="utf-8"))
        _validate_frozen(frozen, snapshots)
    if args.write_final_configuration:
        if args.split != str(Split.DEVELOPMENT):
            raise SystemExit("final configuration must be frozen from development, before holdout")
        if recognition_fixture is not None:
            raise SystemExit(
                "stage-isolated frozen-recognition runs cannot write the final product configuration"
            )
        args.write_final_configuration.parent.mkdir(parents=True, exist_ok=True)
        with args.write_final_configuration.open("x", encoding="utf-8") as stream:
            json.dump({"configurations": [item.to_dict() for item in snapshots]}, stream, indent=2, sort_keys=True)
            stream.write("\n")
    records = asyncio.run(
        run_live(
            settings,
            manifest_path,
            manifest,
            split=args.split,
            recognition_fixture=recognition_fixture,
        )
    )
    write_report(args.output.resolve(), manifest=manifest, cases=selected, records=records, configurations=snapshots)
    return 0


def _validate_frozen(frozen: dict, current) -> None:
    ignored = {"timestamp_utc", "split"}

    def normalized(item: dict) -> dict:
        value = {key: raw for key, raw in item.items() if key not in ignored}
        # Historical frozen configurations predate stage-isolated recognition replay.
        # They are equivalent to LIVE recognition with no fixture hash.
        value.setdefault("recognition_input_mode", "LIVE")
        value.setdefault("recognition_fixture_sha256", None)
        return value

    old = [normalized(item) for item in frozen.get("configurations", [])]
    new = [normalized(item.to_dict()) for item in current]
    if old != new:
        raise SystemExit("current provider/model/prompt/threshold configuration differs from frozen configuration")


if __name__ == "__main__":
    raise SystemExit(main())
