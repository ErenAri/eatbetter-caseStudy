from uuid import uuid4

from app.fixtures import build_canonical_review_fixture, build_review_fixture


def test_review_fixture_candidate_data_carries_provenance_note_not_data_type():
    """Same bug class as the AI/demo provider fix: `data_type` is forwarded to
    the constrained OpenAI selector by meal_canonicalization_service, so a
    human-facing demo-data disclaimer must travel under `provenance_note`
    instead. Demo mode normally pairs with the deterministic canonicalization
    provider so this stayed latent, but the field itself must still be
    correct -- and the rendered text must not change.
    """
    meal = build_review_fixture(uuid4())

    for item in meal.items:
        for candidate in item.candidates:
            assert "data_type" not in (candidate.data or {})
            assert candidate.data["provenance_note"] == "TEST/DEMO DATA — NOT USDA RESULTS"
            assert candidate.display_name() == f"{candidate.name} · TEST/DEMO DATA — NOT USDA RESULTS"


def test_canonical_review_fixture_candidate_data_carries_provenance_note_not_data_type():
    meal = build_canonical_review_fixture(uuid4())

    for item in meal.items:
        for candidate in item.candidates:
            assert "data_type" not in (candidate.data or {})
            assert candidate.data["provenance_note"] == "TEST/DEMO DATA — NOT USDA RESULTS"
            assert candidate.display_name() == f"{candidate.name} · TEST/DEMO DATA — NOT USDA RESULTS"
