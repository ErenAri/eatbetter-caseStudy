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
$env:VISION_PROVIDER = "openai"
$env:CANONICALIZATION_PROVIDER = "openai"
$env:NUTRITION_PROVIDER = "usda"
$env:OPENAI_API_KEY = "..."
$env:USDA_API_KEY = "..."
.\backend\.venv\Scripts\python.exe -m evals.run_benchmark `
  --manifest evals/private/manifest.json `
  --split development `
  --output evals/reports/2026-08-18_dev_v1
```

Each new output directory contains `summary.json`, `cases.jsonl`, `errors.json`, `metrics.json`,
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

No real private manifest is available in this workspace and both required credentials are absent.
Therefore development iteration, configuration freeze, and final holdout results are not measured.
Demo fixtures are prohibited from filling that gap.

Known limitations even after collection: small dataset, likely single evaluator, limited cuisines,
USDA-centered canonical coverage, single-view portion inference, external-model nondeterminism, and no
clinical validation. Fine-tuning is not justified before repeated systematic errors are measured and
prompt/retrieval improvements plateau with enough separated training data.
