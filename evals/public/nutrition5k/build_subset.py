"""Download the fixed, licensed Nutrition5k secondary-evaluation subset.

This script intentionally downloads only twelve overhead RGB images, not the 181 GB archive.
Selection is fixed before any EatBetter model run and follows Nutrition5k's official RGB train/test
split. Generated labels preserve published mass and nutrition strings; the checked-in mappings reflect
separate human USDA review performed before model execution.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen


BASE = "https://storage.googleapis.com/nutrition5k_dataset/nutrition5k_dataset"
ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"
SELECTION = {
    "development": (
        "dish_1556572657",  # single food: olives
        "dish_1557853229",  # single food: eggs
        "dish_1558116001",  # mixed calorie-dense plate
        "dish_1559590202",  # chicken, couscous, salad, asparagus
        "dish_1565637123",  # composite pasta salad
        "dish_1559235815",  # bagel, cream cheese, fruit, eggs
        "dish_1562173200",  # yogurt, milk, fruit, chia
        "dish_1559332418",  # salmon, rice, greens, measured oil
        "dish_1565370004",  # eggs, beans, bacon, measured oil
    ),
    "holdout": (
        "dish_1565811061",  # chicken and vegetables
        "dish_1563478751",  # complex pasta/beef dish with measured oil
        "dish_1562085672",  # simple bread case
    ),
}
VISIBLE_GROUPS = {
    "dish_1556572657": (("olives", ("olives",), ("black olives",), None),),
    "dish_1557853229": (("scrambled eggs", ("eggs",), ("eggs",), "scrambled"),),
    "dish_1558116001": (
        ("almonds", ("almonds",), (), None),
        ("grapes", ("grapes",), (), None),
        ("sausage", ("sausage",), (), "cooked"),
        ("bacon", ("bacon",), (), "cooked"),
        ("potatoes", ("potatoes",), ("roasted potatoes",), "roasted"),
    ),
    "dish_1559590202": (
        ("couscous", ("couscous",), (), "cooked"),
        ("caesar salad", ("caesar salad",), ("salad",), None),
        ("chicken", ("chicken",), ("grilled chicken",), "grilled"),
        ("asparagus", ("asparagus",), (), "cooked"),
    ),
    "dish_1565637123": (("pasta salad", ("pasta salad",), ("pasta",), None),),
    "dish_1559235815": (
        ("cream cheese", ("cream cheese",), (), None),
        ("bagel", ("bagels",), ("bagels",), None),
        ("strawberries", ("strawberries",), (), None),
        ("scrambled eggs", ("eggs",), ("eggs",), "scrambled"),
    ),
    "dish_1562173200": (
        ("pineapple", ("pineapple",), (), None),
        ("yogurt with milk", ("milk", "greek yogurt"), ("yogurt", "plain yogurt", "greek yogurt"), None),
        ("chia seeds", ("chia seeds",), (), None),
    ),
    "dish_1559332418": (
        ("salmon", ("salmon",), ("salmon fillet",), "cooked"),
        ("brown rice", ("brown rice",), ("rice",), "cooked"),
        ("arugula", ("arugula",), ("greens",), None),
    ),
    "dish_1565370004": (
        ("bacon", ("bacon",), (), "cooked"),
        ("scrambled eggs", ("scrambled eggs",), ("eggs",), "scrambled"),
        ("green beans", ("green beans",), (), "cooked"),
    ),
    "dish_1565811061": (
        ("chicken", ("chicken",), ("grilled chicken",), "cooked"),
        ("carrot", ("carrot",), ("shredded carrot",), None),
        ("spinach", ("spinach (raw)",), ("raw spinach", "spinach"), "raw"),
        ("broccoli", ("broccoli",), (), None),
    ),
    "dish_1563478751": (
        ("pasta", ("pasta",), (), "cooked"),
        ("beef", ("beef",), ("sliced beef",), "cooked"),
        ("mushroom", ("mushroom",), ("mushrooms",), "cooked"),
        ("spinach", ("spinach (raw)",), ("spinach",), "cooked"),
    ),
    "dish_1562085672": (("bread", ("bread",), ("slice of bread",), None),),
}
CANONICAL_LABELS = {
    ("olives", None): ("169094", "Olives, ripe, canned (small-extra large)"),
    ("scrambled eggs", "scrambled"): ("2707198", "Egg omelet or scrambled egg, NS as to fat"),
    ("almonds", None): ("2346393", "Nuts, almonds, whole, raw"),
    ("grapes", None): ("2709237", "Grapes, raw"),
    ("sausage", "cooked"): None,
    ("bacon", "cooked"): ("2705887", "Pork bacon, NS as to fresh, smoked or cured, cooked"),
    ("potatoes", "roasted"): ("2709402", "Potato, roasted, NFS"),
    ("couscous", "cooked"): ("2708441", "Couscous, plain, cooked"),
    ("caesar salad", None): None,
    ("chicken", "grilled"): ("2706090", "Chicken fillet, grilled"),
    ("asparagus", "cooked"): ("2709837", "Asparagus, NS as to form, cooked"),
    ("pasta salad", None): None,
    ("cream cheese", None): ("2705760", "Cream cheese, regular, plain"),
    ("bagel", None): ("2707684", "Bagel"),
    ("strawberries", None): ("2709283", "Strawberries, raw"),
    ("pineapple", None): ("2709260", "Pineapple, raw"),
    ("yogurt with milk", None): None,
    ("chia seeds", None): ("2707590", "Chia seeds"),
    ("salmon", "cooked"): ("2706286", "Fish, salmon, baked or broiled"),
    ("brown rice", "cooked"): ("2708409", "Rice, brown, cooked, NS as to fat"),
    ("arugula", None): ("2709791", "Lettuce, arugula, raw"),
    ("green beans", "cooked"): ("2710803", "Green beans, cooked, as ingredient"),
    ("chicken", "cooked"): ("2705954", "Chicken breast, NS as to cooking method, skin not eaten"),
    ("carrot", None): ("2709660", "Carrots, raw"),
    ("spinach", "raw"): ("2709614", "Spinach, raw"),
    ("broccoli", None): ("2709643", "Broccoli, raw"),
    ("pasta", "cooked"): ("2708357", "Pasta, cooked"),
    ("beef", "cooked"): ("2705824", "Beef, steak, NFS"),
    ("mushroom", "cooked"): ("2709938", "Mushrooms, NS as to form, cooked"),
    ("spinach", "cooked"): ("2710791", "Spinach, cooked, as ingredient"),
    ("bread", None): ("2707598", "Bread, white"),
}


def download(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:
        return response.read()


def metadata() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for cafe in ("cafe1", "cafe2"):
        text = download(f"{BASE}/metadata/dish_metadata_{cafe}.csv").decode("utf-8")
        for row in csv.reader(text.splitlines()):
            rows[row[0]] = row
    return rows


def official_split(filename: str) -> set[str]:
    return set(download(f"{BASE}/dish_ids/splits/{filename}").decode("utf-8").splitlines())


def ingredients(row: list[str]) -> list[dict[str, str]]:
    values = []
    for index in range(6, len(row), 7):
        if index + 6 >= len(row):
            continue
        values.append({
            "source_id": row[index],
            "name": row[index + 1],
            "grams": row[index + 2],
            "calories_kcal": row[index + 3],
            "fat_g": row[index + 4],
            "carbs_g": row[index + 5],
            "protein_g": row[index + 6],
        })
    return values


def item_id(position: int, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]
    return f"item_{position:02d}_{slug or 'food'}"


def categories(dish_id: str, values: list[dict[str, str]], calories: float, mass: float) -> list[str]:
    result = ["SIMPLE" if len(VISIBLE_GROUPS[dish_id]) == 1 else "MULTI_COMPONENT"]
    names = " ".join(value["name"].lower() for value in values)
    if calories / mass >= 2 or any(word in names for word in ("oil", "bacon", "cream cheese")):
        result.append("PORTION_SENSITIVE")
    if any(word in names for word in ("oil", "butter", "dressing", "vinegar")):
        result.extend(("SAUCE_OR_OIL", "HIDDEN_INGREDIENT"))
    if any(word in names for word in ("salad", "pizza", "pasta")):
        result.append("COMPOSITE_FOOD")
    return list(dict.fromkeys(result))


def build_case(dish_id: str, split: str, row: list[str], image_sha256: str) -> dict:
    values = ingredients(row)
    by_name = {value["name"]: value for value in values}
    groups = VISIBLE_GROUPS[dish_id]
    visible_source_names = {source_name for _, source_names, _, _ in groups for source_name in source_names}
    missing_sources = visible_source_names - set(by_name)
    if missing_sources:
        raise RuntimeError(f"manual visibility annotation references missing ingredients for {dish_id}: {sorted(missing_sources)}")
    hidden = [value for value in values if value["name"] not in visible_source_names]
    if any((label, preparation) not in CANONICAL_LABELS for label, _, _, preparation in groups):
        raise RuntimeError(f"manual USDA review is missing for a visible label in {dish_id}")
    captured = datetime.fromtimestamp(int(dish_id.removeprefix("dish_")), tz=timezone.utc).date()
    return {
        "case_id": f"nutrition5k_{dish_id}",
        "split": split,
        "categories": categories(dish_id, values, float(row[1]), float(row[2])),
        "image": f"images/{dish_id}.png",
        "items": [
            {
                "item_id": item_id(position, label),
                "label": label,
                "acceptable_aliases": list(aliases),
                "preparation": preparation,
                "portion_truth_g": format(sum((Decimal(by_name[name]["grams"]) for name in source_names), Decimal("0")), "f"),
                "expected_fdc_id": CANONICAL_LABELS[(label, preparation)][0] if CANONICAL_LABELS[(label, preparation)] else None,
                "expected_fdc_name": CANONICAL_LABELS[(label, preparation)][1] if CANONICAL_LABELS[(label, preparation)] else None,
                "acceptable_fdc_ids": [],
                "canonical_ground_truth_status": "VERIFIED" if CANONICAL_LABELS[(label, preparation)] else "UNMAPPABLE",
                "notes": (
                    "Manual visible-component annotation from the downloaded overhead RGB image; source ingredients: "
                    + ", ".join(source_names)
                    + (". USDA candidate independently reviewed before model execution." if CANONICAL_LABELS[(label, preparation)] else ". No single defensible USDA canonical representation due to ambiguous type or composite composition.")
                ),
            }
            for position, (label, source_names, aliases, preparation) in enumerate(groups, start=1)
        ],
        "hidden_ingredients": [
            {
                "name": value["name"],
                "present": True,
                "portion_truth_g": value["grams"],
                "measurement_method": "Published Nutrition5k per-ingredient mass label.",
            }
            for value in hidden
        ],
        "nutrition_truth": {
            "calories_kcal": row[1],
            "protein_g": row[5],
            "carbs_g": row[4],
            "fat_g": row[3],
            "measurement_method": "Published Nutrition5k dish metadata derived from incremental ingredient weighing and USDA nutrition data.",
        },
        "provenance": {
            "captured_by": "Google Research Nutrition5k",
            "capture_device": "Nutrition5k custom scanning rig; overhead RGB-D camera",
            "capture_date": captured.isoformat(),
            "ground_truth_method": "Nutrition5k published per-ingredient mass and dish-level calorie/macronutrient annotations.",
            "consent_or_ownership": "LICENSED",
        },
        "notes": (
            "Public secondary benchmark; CC BY 4.0 Nutrition5k. Not equivalent to ordinary phone capture. "
            f"Downloaded image SHA-256: {image_sha256}."
        ),
    }


def main() -> None:
    rows = metadata()
    train = official_split("rgb_train_ids.txt")
    test = official_split("rgb_test_ids.txt")
    if not set(SELECTION["development"]).issubset(train):
        raise RuntimeError("development selection drifted from official Nutrition5k RGB train split")
    if not set(SELECTION["holdout"]).issubset(test):
        raise RuntimeError("holdout selection drifted from official Nutrition5k RGB test split")
    if set(SELECTION["development"]) & set(SELECTION["holdout"]):
        raise RuntimeError("public development and holdout selections overlap")

    IMAGES.mkdir(parents=True, exist_ok=True)
    cases = []
    source_files = []
    for split, dish_ids in SELECTION.items():
        for dish_id in dish_ids:
            image_url = f"{BASE}/imagery/realsense_overhead/{dish_id}/rgb.png"
            image = download(image_url)
            if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError(f"official image is not PNG: {dish_id}")
            image_path = IMAGES / f"{dish_id}.png"
            image_path.write_bytes(image)
            digest = hashlib.sha256(image).hexdigest()
            cases.append(build_case(dish_id, split, rows[dish_id], digest))
            source_files.append({"dish_id": dish_id, "split": split, "url": image_url, "sha256": digest})

    manifest = {"schema_version": 1, "dataset_version": "nutrition5k-public-secondary-v1", "cases": cases}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    source = {
        "dataset": "Nutrition5k",
        "official_repository": "https://github.com/google-research-datasets/Nutrition5k",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "selection_policy": "Fixed before model execution; 9 official RGB train IDs and 3 official RGB test IDs.",
        "files": source_files,
    }
    (ROOT / "sources.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(cases), "development": len(SELECTION["development"]), "holdout": len(SELECTION["holdout"])}, sort_keys=True))


if __name__ == "__main__":
    main()
