from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.canonical_equivalence import file_sha256, load_review_packet


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create an intentionally incomplete equivalence adjudication template."
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    packet_path = args.packet.resolve()
    packet = load_review_packet(packet_path)
    template = {
        "schema_version": 1,
        "dataset_version": packet.dataset_version,
        "split": packet.split,
        "review_packet_sha256": file_sha256(packet_path),
        "reviewer": "REPLACE_WITH_INDEPENDENT_REVIEWER",
        "reviewed_utc": "REPLACE_WITH_ISO8601_TIMESTAMP",
        "adjudications": [
            {
                "pair_id": pair.pair_id,
                "decision": None,
                "rationale": None,
            }
            for pair in packet.pairs
        ],
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(template, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        f"Wrote adjudication template for {len(packet.pairs)} pairs. "
        "The file is intentionally invalid until every decision/rationale is completed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
