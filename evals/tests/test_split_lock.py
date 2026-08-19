import json
from pathlib import Path

from evals.create_split_lock import build_lock, dataset_hash
from evals.tests.test_p8_dataset import manifest, valid_case


def test_split_lock_hashes_manifest_images_and_preserves_ids(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "meal_001.jpg").write_bytes(b"\xff\xd8\xfffirst")
    holdout = valid_case(case_id="meal_002", split="holdout", image="images/meal_002.jpg")
    (images / "meal_002.jpg").write_bytes(b"\xff\xd8\xffsecond")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest([valid_case(), holdout])), encoding="utf-8")
    lock = build_lock(path)
    assert lock["case_ids"] == ["meal_001", "meal_002"]
    assert lock["development_ids"] == ["meal_001"]
    assert lock["holdout_ids"] == ["meal_002"]
    before = dataset_hash(path)
    (images / "meal_001.jpg").write_bytes(b"\xff\xd8\xffchanged")
    assert dataset_hash(path) != before


def test_schema_v2_hash_is_stable_across_line_endings(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "meal_001.jpg").write_bytes(b"\xff\xd8\xffsame-image")
    path = tmp_path / "manifest.json"
    value = manifest([valid_case()])
    value["schema_version"] = 2
    pretty = json.dumps(value, indent=2) + "\n"
    path.write_bytes(pretty.encode("utf-8"))
    lf_hash = dataset_hash(path)
    path.write_bytes(pretty.replace("\n", "\r\n").encode("utf-8"))
    crlf_hash = dataset_hash(path)
    assert crlf_hash == lf_hash
    lock = build_lock(path)
    assert lock["hash_scheme"] == "canonical-json-v2+image-sha256"
