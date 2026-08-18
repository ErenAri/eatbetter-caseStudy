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
