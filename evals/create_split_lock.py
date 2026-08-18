from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from evals.dataset import Split, load_manifest


def dataset_hash(manifest_path: Path) -> str:
    manifest = load_manifest(manifest_path)
    digest = hashlib.sha256()
    digest.update(manifest_path.read_bytes())
    for case in sorted(manifest.cases, key=lambda value: value.case_id):
        image_path = (manifest_path.parent / case.image).resolve()
        digest.update(case.case_id.encode("utf-8"))
        digest.update(hashlib.sha256(image_path.read_bytes()).digest())
    return digest.hexdigest()


def build_lock(manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    all_ids = [case.case_id for case in manifest.cases]
    development_ids = [case.case_id for case in manifest.cases if case.split == Split.DEVELOPMENT]
    holdout_ids = [case.case_id for case in manifest.cases if case.split == Split.HOLDOUT]
    return {
        "schema_version": 1,
        "dataset_version": manifest.dataset_version,
        "dataset_sha256": dataset_hash(manifest_path),
        "case_ids": all_ids,
        "development_ids": development_ids,
        "holdout_ids": holdout_ids,
        "case_count": len(all_ids),
        "development_count": len(development_ids),
        "holdout_count": len(holdout_ids),
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an immutable pre-benchmark dataset split lock.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = build_lock(args.manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(lock, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: lock[key] for key in ("dataset_version", "dataset_sha256", "case_count", "development_count", "holdout_count")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
