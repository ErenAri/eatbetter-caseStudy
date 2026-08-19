from __future__ import annotations

from evals.build_equivalence_review_packet import _pair_specs
from evals.canonical_equivalence import (
    BlindedReviewPair,
    EquivalenceAdjudication,
    EquivalenceAdjudicationSet,
    EquivalenceDecision,
    EquivalenceReviewKey,
    EquivalenceReviewPacket,
    FoodSnapshot,
    ReviewKeyEntry,
    equivalent_candidate_ids_by_item,
    reference_goes_first,
    stable_pair_id,
    validate_adjudications,
)
from evals.dataset import DatasetManifest
from evals.score_canonical_equivalence import score
from evals.tests.test_p8_dataset import manifest, valid_case


def dataset() -> DatasetManifest:
    return DatasetManifest.model_validate(manifest([valid_case()]))


def candidate_records():
    return {
        "meal_001": {
            "case_id": "meal_001",
            "status": "completed",
            "configurations": {
                "HYBRID_AUTO": {
                    "items": [
                        {
                            "observed_name": "banana",
                            "candidates": [
                                {"rank": 1, "food_id": "999", "name": "Banana, raw"},
                                {"rank": 2, "food_id": "173944", "name": "Bananas, raw"},
                            ],
                            "selected_rank": 1,
                            "selected_food_id": "999",
                            "match_quality": "EXACT",
                        }
                    ]
                }
            },
        }
    }


def pair_id() -> str:
    return stable_pair_id(
        dataset_version="p8-v1",
        case_id="meal_001",
        item_id="banana",
        reference_fdc_id="173944",
        candidate_fdc_id="999",
    )


def packet() -> EquivalenceReviewPacket:
    return EquivalenceReviewPacket(
        dataset_version="p8-v1",
        split="development",
        source_manifest_sha256="a" * 64,
        source_candidate_artifact_sha256="b" * 64,
        created_utc="2026-08-20T00:00:00+00:00",
        blindness_note="Outcome-blinded review packet for independent canonical equivalence review.",
        pairs=[
            BlindedReviewPair(
                pair_id=pair_id(),
                target_label="banana",
                target_preparation="raw",
                food_a=FoodSnapshot(fdc_id="173944", name="Bananas, raw"),
                food_b=FoodSnapshot(fdc_id="999", name="Banana, raw"),
            )
        ],
    )


def key() -> EquivalenceReviewKey:
    return EquivalenceReviewKey(
        dataset_version="p8-v1",
        split="development",
        review_packet_sha256="c" * 64,
        source_manifest_sha256="a" * 64,
        source_candidate_artifact_sha256="b" * 64,
        warning="Do not share this role key with the independent reviewer.",
        entries=[
            ReviewKeyEntry(
                pair_id=pair_id(),
                case_id="meal_001",
                item_id="banana",
                reference_fdc_id="173944",
                candidate_fdc_id="999",
            )
        ],
    )


def adjudications(decision: EquivalenceDecision) -> EquivalenceAdjudicationSet:
    return EquivalenceAdjudicationSet(
        dataset_version="p8-v1",
        split="development",
        review_packet_sha256="c" * 64,
        reviewer="independent-reviewer",
        reviewed_utc="2026-08-20T00:00:00+00:00",
        adjudications=[
            EquivalenceAdjudication(
                pair_id=pair_id(),
                decision=decision,
                rationale="Same visible food and preparation for meal logging.",
            )
        ],
    )


def test_pair_specs_strip_selector_outcome_and_skip_already_exact_ids() -> None:
    specs = _pair_specs(
        dataset(), candidate_records(), split="development", configuration="HYBRID_AUTO"
    )

    assert specs == [
        {
            "case_id": "meal_001",
            "item_id": "banana",
            "target_label": "banana",
            "target_preparation": "raw",
            "reference_fdc_id": "173944",
            "candidate_fdc_id": "999",
        }
    ]
    assert "selected_food_id" not in specs[0]
    assert "rank" not in specs[0]


def test_pair_role_blinding_is_deterministic() -> None:
    value = pair_id()
    assert reference_goes_first(value) == reference_goes_first(value)
    assert len(value) == 64


def test_equivalent_decision_expands_secondary_ids_only() -> None:
    expanded = equivalent_candidate_ids_by_item(key(), adjudications(EquivalenceDecision.EQUIVALENT))
    assert expanded[("meal_001", "banana")] == {"999"}

    uncertain = equivalent_candidate_ids_by_item(key(), adjudications(EquivalenceDecision.UNCERTAIN))
    rejected = equivalent_candidate_ids_by_item(key(), adjudications(EquivalenceDecision.NOT_EQUIVALENT))
    assert uncertain == {}
    assert rejected == {}


def test_secondary_scoring_preserves_exact_metric_and_adds_equivalence_metric() -> None:
    result = score(
        manifest=dataset(),
        records=candidate_records(),
        configuration="HYBRID_AUTO",
        equivalent_by_item={("meal_001", "banana"): {"999"}},
    )

    assert result["retrieval"]["exact_recall_at_1"]["value"] == 0.0
    assert result["retrieval"]["exact_recall_at_5"]["value"] == 1.0
    assert result["retrieval"]["equivalence_recall_at_1"]["value"] == 1.0
    assert result["selector"]["exact_accuracy"]["value"] == 0.0
    assert result["selector"]["equivalence_accuracy"]["value"] == 1.0


def test_artifact_validation_requires_complete_matching_pair_set() -> None:
    review_packet = packet()
    review_key = key()
    valid = adjudications(EquivalenceDecision.EQUIVALENT)
    validate_adjudications(
        packet=review_packet,
        packet_sha256="c" * 64,
        key=review_key,
        adjudications=valid,
    )

    incomplete = valid.model_copy(update={"adjudications": []})
    try:
        validate_adjudications(
            packet=review_packet,
            packet_sha256="c" * 64,
            key=review_key,
            adjudications=incomplete,
        )
    except ValueError as error:
        assert "pair set mismatch" in str(error)
    else:
        raise AssertionError("incomplete adjudication set must be rejected")
