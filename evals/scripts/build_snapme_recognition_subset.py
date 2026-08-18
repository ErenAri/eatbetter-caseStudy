"""Build a private, review-ready phone-photo subset from the USDA SNAPMe archive.

SNAPMe amounts come from linked ASA24 dietary records, not kitchen-scale measurements. This builder
therefore preserves them as source context but never promotes them to measured portion truth. The
result is not benchmark-ready until a human reviews which recorded foods are visibly supported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tarfile
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


EXPECTED_ARCHIVE_MD5 = "95383fd42b78eb45adbad03c7673e8f7"
SOURCE_URL = "https://agdatacommons.nal.usda.gov/ndownloader/files/44532971"
SOURCE_DOI = "https://doi.org/10.15482/USDA.ADC/1528346"
SEED = "eatbetter-snapme-recognition-v1"
DATE_PATTERN = re.compile(
    r"snapme_nut_db/(?P<subject>\d+)_QC/(?P<date>\d{6})_day(?P<day>[123])"
)


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def load_groups(link_file: Path) -> dict[tuple[str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with link_file.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["packaged_food"] == "0" and row["filename"].lower().endswith(
                (".jpg", ".jpeg", ".png")
            ):
                groups[(row["subject_id"], row["filename"])].append(row)
    return dict(groups)


def select_cases(groups: dict[tuple[str, str], list[dict[str, str]]], count: int) -> list[dict]:
    by_subject: dict[str, list[tuple[str, list[dict[str, str]]]]] = defaultdict(list)
    for (subject, filename), rows in groups.items():
        by_subject[subject].append((filename, rows))
    if count > len(by_subject):
        raise ValueError(f"requested {count} cases but only {len(by_subject)} participants exist")

    chosen_subjects = sorted(by_subject, key=stable_key)[:count]
    development_count = round(count * 0.75)
    cases = []
    for position, subject in enumerate(chosen_subjects):
        candidates = by_subject[subject]
        bucket = position % 4

        def in_bucket(item_count: int) -> bool:
            return (
                (bucket == 0 and item_count == 1)
                or (bucket == 1 and 2 <= item_count <= 3)
                or (bucket == 2 and 4 <= item_count <= 6)
                or (bucket == 3 and item_count >= 7)
            )

        preferred = [entry for entry in candidates if in_bucket(len(entry[1]))] or candidates
        filename, rows = min(preferred, key=lambda entry: stable_key(f"{subject}:{entry[0]}"))
        day = rows[0]["snapme_study_day"]
        if any(row["snapme_study_day"] != day for row in rows):
            raise ValueError(f"one image maps to multiple study days: {filename}")
        cases.append(
            {
                "case_id": f"snapme_{Path(filename).stem}",
                "split": "development" if position < development_count else "holdout",
                "subject_key": hashlib.sha256(subject.encode()).hexdigest()[:16],
                "source_filename": filename,
                "study_day": day,
                "recorded_items": [
                    {
                        "food_code": row["FoodCode"],
                        "description": row["Food_Description"],
                        "asa24_record_amount_g": row["FoodAmt"],
                        "calories_kcal": row["KCAL"],
                        "protein_g": row["PROT"],
                        "fat_g": row["TFAT"],
                        "carbs_g": row["CARB"],
                    }
                    for row in rows
                ],
            }
        )
    return cases


def archive_index(archive: Path) -> tuple[set[str], dict[tuple[str, str], str]]:
    members: set[str] = set()
    dates: dict[tuple[str, str], str] = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            members.add(member.name)
            match = DATE_PATTERN.search(member.name)
            if match:
                key = (f"SNAPME{match['subject']}", match["day"])
                parsed = datetime.strptime(match["date"], "%y%m%d").date().isoformat()
                prior = dates.setdefault(key, parsed)
                if prior != parsed:
                    raise ValueError(f"conflicting capture dates for {key}: {prior}, {parsed}")
    return members, dates


def extract_selected(archive: Path, output: Path, cases: list[dict]) -> None:
    image_dir = output / "images"
    image_dir.mkdir(parents=True, exist_ok=False)
    wanted = {
        f"snapme_db_09Dec2022/snapme_cs_db/before_photos/{case['source_filename']}": case
        for case in cases
    }
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            case = wanted.get(member.name)
            if case is None:
                continue
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError(f"selected image is not a regular file: {member.name}")
            target = image_dir / case["source_filename"]
            digest = hashlib.sha256()
            with target.open("xb") as stream:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    stream.write(chunk)
            case["image"] = f"images/{target.name}"
            case["image_sha256"] = digest.hexdigest()
            del wanted[member.name]
    if wanted:
        raise ValueError(f"selected archive images are missing: {sorted(wanted)}")


def write_outputs(output: Path, archive: Path, cases: list[dict], dates: dict) -> None:
    for case in cases:
        subject_number = case["subject_key"]
        # Resolve the date before discarding the private source participant identifier from output.
        source_subject = next(
            subject
            for subject in {row_subject for row_subject, _ in dates}
            if hashlib.sha256(subject.encode()).hexdigest()[:16] == subject_number
        )
        case["capture_date"] = dates[(source_subject, case["study_day"])]
        case["eligibility"] = {
            "recognition": "PENDING_MANUAL_VISIBLE_LABEL_REVIEW",
            "portion": "INELIGIBLE_ASA24_NOT_WEIGHED",
            "hidden_ingredients": "INELIGIBLE_NOT_INDEPENDENTLY_MEASURED",
            "nutrition": "SECONDARY_ASA24_RECORD_ONLY",
            "canonical": "UNVERIFIED",
        }

    archive_sha256 = file_hash(archive)
    selection = {
        "schema_version": 1,
        "dataset_version": "snapme-phone-recognition-private-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "SNAPMe",
            "doi": SOURCE_DOI,
            "download_url": SOURCE_URL,
            "license": "CC BY-SA 4.0",
            "archive_bytes": archive.stat().st_size,
            "archive_md5": EXPECTED_ARCHIVE_MD5,
            "archive_sha256": archive_sha256,
        },
        "selection": {
            "seed": SEED,
            "policy": "One before-photo per participant; deterministic complexity buckets; participant-disjoint 75/25 split.",
            "case_count": len(cases),
            "development_count": sum(case["split"] == "development" for case in cases),
            "holdout_count": sum(case["split"] == "holdout" for case in cases),
        },
        "truth_boundary": (
            "ASA24 amounts and nutrition are dietary-record-derived, not weighed. Recorded line items "
            "may include visually hidden recipe components. No case is benchmark-eligible until "
            "independent visible-label review; portion and hidden-ingredient metrics remain ineligible."
        ),
        "cases": cases,
    }
    selection_path = output / "selection.json"
    selection_path.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")

    with (output / "review_queue.csv").open("x", encoding="utf-8", newline="") as stream:
        fields = [
            "case_id",
            "split",
            "image",
            "capture_date",
            "recorded_descriptions",
            "visible_labels",
            "reviewer",
            "reviewed_at",
            "review_notes",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case["case_id"],
                    "split": case["split"],
                    "image": case["image"],
                    "capture_date": case["capture_date"],
                    "recorded_descriptions": " | ".join(
                        item["description"] for item in case["recorded_items"]
                    ),
                    "visible_labels": "",
                    "reviewer": "",
                    "reviewed_at": "",
                    "review_notes": "",
                }
            )

    lock_payload = {
        "dataset_version": selection["dataset_version"],
        "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        "case_ids": [case["case_id"] for case in cases],
        "development_ids": [case["case_id"] for case in cases if case["split"] == "development"],
        "holdout_ids": [case["case_id"] for case in cases if case["split"] == "holdout"],
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "split_lock.json").write_text(
        json.dumps(lock_payload, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(
        "# Private SNAPMe phone-photo recognition subset\n\n"
        "This directory contains a deterministic, participant-disjoint 40-photo subset of the "
        "USDA SNAPMe dataset. It is private and Git-ignored. Source assets are CC BY-SA 4.0.\n\n"
        "This is a recognition review queue, not measured portion ground truth. `FoodAmt` and "
        "nutrition values are linked ASA24 dietary-record outputs. They were not obtained with a "
        "kitchen scale, and recipe line items may not be visible. Do not populate the production "
        "evaluation manifest until `review_queue.csv` has independent visible-label review. Never "
        "use these cases for portion or hidden-ingredient accuracy claims.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--link-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=40)
    args = parser.parse_args()
    archive = args.archive.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    if file_hash(archive, "md5") != EXPECTED_ARCHIVE_MD5:
        raise SystemExit("SNAPMe archive MD5 does not match the publisher checksum")
    groups = load_groups(args.link_file.resolve())
    cases = select_cases(groups, args.count)
    members, dates = archive_index(archive)
    expected = {
        f"snapme_db_09Dec2022/snapme_cs_db/before_photos/{case['source_filename']}"
        for case in cases
    }
    missing = expected - members
    if missing:
        raise SystemExit(f"selected photos missing from archive: {sorted(missing)}")
    missing_dates = [
        (case["subject_key"], case["study_day"])
        for case in cases
        if not any(
            hashlib.sha256(subject.encode()).hexdigest()[:16] == case["subject_key"]
            and day == case["study_day"]
            for subject, day in dates
        )
    ]
    if missing_dates:
        raise SystemExit(f"capture dates missing for selected cases: {missing_dates}")
    output.mkdir(parents=True, exist_ok=False)
    extract_selected(archive, output, cases)
    write_outputs(output, archive, cases, dates)
    print(
        json.dumps(
            {
                "output": str(output),
                "cases": len(cases),
                "development": sum(case["split"] == "development" for case in cases),
                "holdout": sum(case["split"] == "holdout" for case in cases),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
