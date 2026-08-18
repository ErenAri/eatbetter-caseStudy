# Real-world evaluation protocol

The primary evaluation unit is one ordinary, consented smartphone meal photo. Target 30–40 meals,
split approximately 75% development and 25% case-study holdout. Split by meal and contributor; never
place the same `case_id` in both. Include simple foods without letting them dominate, multi-component
meals, calorie-dense portions, measured sauce/oil, composite dishes, Turkish/local foods, difficult
images, and non-meal negatives.

## Collection and ground truth

- Use a normal eating angle, ordinary lighting, and one phone photo—the same conditions as the app.
- Weigh evaluable portions with a kitchen scale. Serialize decimal values as strings. A missing weight
  is `null` and is excluded from portion metrics.
- Measure oil, butter, dressing, sauce, or cheese directly or by a documented before/after method.
- Independently inspect USDA search and detail results with `backend/scripts/search_usda.py`. Mark an
  item `VERIFIED` only after human review; the pipeline's own choice cannot label itself. Use
  `UNMAPPABLE` when no defensible USDA representation exists.
- Derive meal nutrition truth independently from verified ingredients and measured amounts. Never
  derive it from the prediction being graded.
- Record only pseudonymous provenance and ownership/consent. Do not collect people or private context.

The strict contract in `dataset.py` rejects missing images, unsafe relative paths, duplicate case or
item IDs, development/holdout overlap, invalid categories/splits/FDC IDs, negative weights, and
inconsistent verified/unmappable labels. Raw labels are read-only inputs; run output goes elsewhere.

## Privacy

`evals/private/**` is ignored by Git. Keep real manifests and images there unless publication is
separately and intentionally approved. Public reports contain aggregate metrics and image reference
IDs, not image bytes. The checked-in example is synthetic schema documentation and has no result.

## Configurations and execution

- `BASELINE_TOP1`: same P4 observation and P3 ranked candidates, always rank 1, portion midpoint, no
  selective clarification. This isolates the downstream value of P5/P6.
- `HYBRID_AUTO`: P4→P3→P5→P6 state captured before human answers.
- `HYBRID_ORACLE_HITL`: clearly labeled evaluation-only upper bound. Ground truth becomes visible only
  after P6 generated a question, and only answers representable questions. Pre-HITL output remains
  unchanged.

Real runs reject demo or unconfigured providers. From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_benchmark `
  --manifest evals/private/manifest.json `
  --split development `
  --output evals/reports/2026-08-18_dev_v1
```

The local runner reads secrets from ignored `backend/.env`; explicitly exported process variables
override that file. Each new output directory contains `summary.json`, `cases.jsonl`, `errors.json`, `metrics.json`,
`configuration.json`, and `summary.md`; existing outputs are never overwritten. After 2–3 isolated
development iterations, create `evals/reports/final_configuration.json` with
`--write-final-configuration`. A holdout run requires that file via `--frozen-configuration` and
rejects configuration drift.

Metrics are stage-specific and retain numerator/denominator or label count. Null labels are excluded,
MAPE excludes zero truth, retrieval excludes unverified/unmappable labels, selector metrics exclude
retrieval misses, and provider timeouts count as infrastructure failures. Materially wrong auto-accept
means an incorrect canonical item or calorie error above 20%. Interval coverage is reported beside
median interval width. Cost is omitted because no reliable versioned pricing configuration exists.

## Current dataset status

The private product dataset remains empty. A fixed public secondary subset is checked in under
`evals/public/nutrition5k/`: 12 licensed rig-captured dishes, split into nine development and three
untouched holdout cases. All have published measured portions; 30/34 visible item instances have
independently reviewed USDA mappings and four are `UNMAPPABLE`. The live benchmark ran with real
OpenAI and USDA providers, one prompt iteration, a frozen configuration, and no holdout rerun. See
`docs/measured-evaluation.md` for measured aggregates and limitations. Raw per-case run directories
and credentials remain ignored.

Known limitations: a very small public subset, rig capture rather than ordinary phone photos, a
three-meal holdout, single evaluator, limited cuisines,
USDA-centered canonical coverage, single-view portion inference, external-model nondeterminism, and no
clinical validation. Fine-tuning is not justified before repeated systematic errors are measured and
prompt/retrieval improvements plateau with enough separated training data.

## Optional SNAPMe phone-photo recognition queue

`scripts/build_snapme_recognition_subset.py` creates a deterministic 40-photo private intake queue
from the USDA SNAPMe archive: one “before” photo per participant, 30 development and 10 participant-
disjoint holdout cases. The source archive is CC BY-SA 4.0 and belongs under ignored
`evals/private/snapme/`; do not commit it or the extracted photos.

SNAPMe links phone photos to same-day ASA24 food records. Its `FoodAmt` and nutrition fields are
dietary-record-derived, not kitchen-scale measurements, and record lines may describe visually hidden
recipe components. The builder therefore marks recognition labels pending manual visible-label review,
canonical truth unverified, and portion/hidden-ingredient truth ineligible. It must not be used to
claim measured portion accuracy.

```powershell
.\backend\.venv\Scripts\python.exe evals\scripts\build_snapme_recognition_subset.py `
  --archive evals\private\snapme\source\snapme_db_09Dec2022.tar.gz `
  --link-file evals\private\snapme\metadata\snapme_db_09Dec2022\snapme_cs_db\master_SNAPME_linkfile.csv `
  --output evals\private\snapme\subset_v1 `
  --count 40
```
