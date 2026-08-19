# Canonical-equivalence secondary metric

The frozen exact-FDC benchmark remains the primary retrieval/canonicalization metric. This review
protocol adds a **separate secondary metric** for cases where FoodData Central contains multiple
representations that may be equally acceptable for the visible meal observation.

This protocol must never be used to retrofit `acceptable_fdc_ids` after seeing benchmark outcomes.
The manifest remains unchanged.

## Why this exists

Exact FDC identity can distinguish records that are operationally interchangeable for a photo meal
logger. Examples can include two records with the same food/preparation description from different
FoodData Central data types, or a generic dietary-intake record and a minimally different reference
record. Exact identity is still useful for reproducibility, so it is preserved rather than replaced.

The secondary question is narrower:

> Would either FoodData Central record be an acceptable canonical representation of the same visible
> food at the same preparation/specificity level for this meal-logging observation?

## Independence and blinding

The reviewer receives only:

- target food label,
- target preparation when available,
- FoodData Central snapshot A,
- FoodData Central snapshot B,
- opaque `pair_id`.

The reviewer packet intentionally omits:

- retrieval rank,
- which record is the frozen reference,
- which record came from the evaluated candidate pool,
- selector choice,
- match quality,
- benchmark errors or metrics,
- whether either answer would improve a measured score.

The private key mapping A/B pairs back to reference/candidate roles must **not** be shared with the
reviewer until adjudication is sealed.

The person producing/tuning the benchmark should not also act as the claimed independent reviewer.
If no independent reviewer is available, the artifact may be used only as exploratory analysis and
must not be presented as an independently adjudicated metric.

## Decision rubric

Each pair gets exactly one decision.

### `EQUIVALENT`

Use only when both records are acceptable representations of the same visible food for the target
observation. Required considerations:

- same core food identity,
- no conflicting visible preparation,
- no added composite food identity that changes what the user ate,
- no materially different product/form that would require information unavailable from the photo.

Matching calories/macros can support equivalence but **nutrition similarity alone is not sufficient**.

### `NOT_EQUIVALENT`

Use when the records differ materially, including:

- different food identity,
- composite vs atomic food,
- conflicting preparation,
- materially different ingredient/fat/sauce state,
- branded/specialized variant not supported by the observation,
- another difference that would make substitution misleading in a meal log.

### `UNCERTAIN`

Use when the supplied FoodData Central evidence is insufficient to make a defensible equivalence
judgment. `UNCERTAIN` never counts as a secondary match.

## 1. Build the blinded development packet

Use a **frozen development candidate artifact**. Do not use holdout.

For the score-first P1 run:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.build_equivalence_review_packet `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --cases-jsonl evals\reports\2026-08-19_dev_ranker_score_first_pr_b\cases.jsonl `
  --split development `
  --configuration HYBRID_AUTO `
  --packet-output evals\private\equivalence\score_first_review_packet.json `
  --key-output evals\private\equivalence\score_first_review_key.json
```

The builder:

- considers only recognition-matched items with frozen `VERIFIED` canonical truth,
- excludes IDs already accepted by the frozen manifest,
- snapshots authoritative FoodData Central detail for both records,
- removes rank/selection outcome information,
- deterministically randomizes which side contains the reference,
- writes immutable files and reports the packet SHA-256.

The review packet and key are bound to the exact manifest and exact `cases.jsonl` bytes by SHA-256.

## 2. Create the reviewer template

```powershell
.\backend\.venv\Scripts\python.exe -m evals.create_equivalence_adjudication_template `
  --packet evals\private\equivalence\score_first_review_packet.json `
  --output evals\private\equivalence\score_first_adjudications.json
```

Give the independent reviewer **only**:

- `score_first_review_packet.json`
- `score_first_adjudications.json`
- this decision rubric

Do not give them the private key or benchmark reports.

The template is intentionally invalid until every `decision`, `rationale`, `reviewer`, and
`reviewed_utc` field is completed. Use ISO-8601 for `reviewed_utc`.

## 3. Score the secondary metric

After independent review is complete:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.score_canonical_equivalence `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --cases-jsonl evals\reports\2026-08-19_dev_ranker_score_first_pr_b\cases.jsonl `
  --packet evals\private\equivalence\score_first_review_packet.json `
  --key evals\private\equivalence\score_first_review_key.json `
  --adjudications evals\private\equivalence\score_first_adjudications.json `
  --configuration HYBRID_AUTO `
  --output evals\reports\2026-08-20_score_first_equivalence_metrics.json
```

The scorer fails closed if:

- packet/key/adjudication hashes do not match,
- manifest or candidate artifact bytes changed,
- a pair is missing or duplicated,
- any decision is invalid,
- the artifacts refer to a different dataset/split.

## Metric policy

The output reports both metric families side-by-side:

- `exact_recall_at_1/3/5`
- `equivalence_recall_at_1/3/5`
- exact selector accuracy
- equivalence-aware selector accuracy

Only `EQUIVALENT` expands the secondary acceptable set. `NOT_EQUIVALENT` and `UNCERTAIN` never do.

The exact-FDC result is never overwritten or relabeled. The secondary metric should be described as
"independently adjudicated canonical-equivalence" only when the independence rule above was actually
followed.

## Versioning

Do not edit a completed packet/adjudication in place after scoring. If the review policy, candidate
artifact, manifest, or evidence changes, create a new version with a new SHA-256 and retain the prior
artifact for auditability.
