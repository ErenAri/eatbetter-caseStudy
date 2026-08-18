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
from evals.reporting import write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P8 real-provider meal benchmark.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=[str(value) for value in Split], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--frozen-configuration", type=Path, help="Required for holdout; created before holdout inspection.")
    parser.add_argument("--write-final-configuration", type=Path, help="Write the chosen development configuration once.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    selected = [case for case in manifest.cases if str(case.split) == args.split]
    if not selected:
        raise SystemExit(f"manifest has no {args.split} cases")
    settings = Settings.from_env()
    validate_real_providers(settings)
    snapshots = [snapshot(settings, configuration=name, dataset_version=manifest.dataset_version, split=args.split, seed=args.seed) for name in ConfigurationName]
    if args.split == str(Split.HOLDOUT):
        if not args.frozen_configuration or not args.frozen_configuration.is_file():
            raise SystemExit("holdout requires --frozen-configuration written before the holdout run")
        frozen = json.loads(args.frozen_configuration.read_text(encoding="utf-8"))
        _validate_frozen(frozen, snapshots)
    if args.write_final_configuration:
        if args.split != str(Split.DEVELOPMENT):
            raise SystemExit("final configuration must be frozen from development, before holdout")
        args.write_final_configuration.parent.mkdir(parents=True, exist_ok=True)
        with args.write_final_configuration.open("x", encoding="utf-8") as stream:
            json.dump({"configurations": [item.to_dict() for item in snapshots]}, stream, indent=2, sort_keys=True)
            stream.write("\n")
    records = asyncio.run(run_live(settings, args.manifest.resolve(), manifest, split=args.split))
    write_report(args.output.resolve(), manifest=manifest, cases=selected, records=records, configurations=snapshots)
    return 0


def _validate_frozen(frozen: dict, current) -> None:
    ignored = {"timestamp_utc", "split"}
    old = [{key: value for key, value in item.items() if key not in ignored} for item in frozen.get("configurations", [])]
    new = [{key: value for key, value in item.to_dict().items() if key not in ignored} for item in current]
    if old != new:
        raise SystemExit("current provider/model/prompt/threshold configuration differs from frozen configuration")


if __name__ == "__main__":
    raise SystemExit(main())
