from evals.scripts.build_snapme_recognition_subset import select_cases


def row(subject: int, filename: str, item: int) -> dict[str, str]:
    return {
        "subject_id": f"SNAPME{subject}",
        "filename": filename,
        "snapme_study_day": "1",
        "FoodCode": str(1000 + item),
        "Food_Description": f"food {item}",
        "FoodAmt": "100",
        "KCAL": "50",
        "PROT": "1",
        "TFAT": "2",
        "CARB": "3",
    }


def test_selection_is_deterministic_and_participant_disjoint():
    groups = {}
    for subject in range(1000, 1045):
        for photo, item_count in enumerate((1, 2, 4, 7), start=1):
            filename = f"{subject}_{photo}.jpeg"
            groups[(f"SNAPME{subject}", filename)] = [
                row(subject, filename, item) for item in range(item_count)
            ]

    first = select_cases(groups, 40)
    second = select_cases(groups, 40)
    assert first == second
    assert sum(case["split"] == "development" for case in first) == 30
    assert sum(case["split"] == "holdout" for case in first) == 10
    assert len({case["subject_key"] for case in first}) == 40
    development = {case["subject_key"] for case in first if case["split"] == "development"}
    holdout = {case["subject_key"] for case in first if case["split"] == "holdout"}
    assert not development & holdout
