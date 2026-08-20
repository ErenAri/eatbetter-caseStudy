# Real-world evaluation protocol

The primary product evaluation unit is one ordinary, consented smartphone meal photo. Target 30–40 meals, split approximately 75% development and 25% final holdout. Split by meal and contributor; never place the same `case_id` in both. Include simple foods without letting them dominate, multi-component meals, calorie-dense portions, measured sauce/oil, composite dishes, Turkish/local foods, difficult images, and non-meal negatives.

## Collection and ground truth

- Use a normal eating angle, ordinary lighting, and one phone photo—the same conditions as the app.
- Weigh evaluable portions with a kitchen scale. Serialize decimal values as strings. A missing weight is `null` and is excluded from portion metrics.
- Measure oil, butter, dressing, sauce, or cheese directly or by a documented before/after method.
- Independently inspect USDA search and detail results with `backend/scripts/search_usda.py`. Mark an item `VERIFIED` only after human review; the pipeline's own choice cannot label itself. Use `UNMAPPABLE` when no defensible USDA representation exists.
- Derive meal nutrition truth independently from verified ingredients and measured amounts. Never derive it from the prediction being graded.
- Record only pseudonymous provenance and ownership/consent. Do not collect people or private context.

The strict contract in `dataset.py` rejects missing images, unsafe relative paths, duplicate case/item IDs, development/holdout overlap, invalid categories/splits/FDC IDs, negative weights, and inconsistent verified/unmappable labels. Raw labels are read-only inputs; run output goes elsewhere.

## Privacy

`evals/private/**` is ignored by Git. Keep real manifests and images there unless publication is separately and intentionally approved. Public reports contain aggregate metrics and image reference IDs, not image bytes.

## Configurations

- `BASELINE_TOP1`: same vision observation and ranked candidates, always rank 1, portion midpoint, no selective clarification.
- `HYBRID_AUTO`: production recognition → retrieval → constrained canonicalization → deterministic uncertainty state captured before human answers.
- `HYBRID_ORACLE_HITL`: evaluation-only staged upper bound. Ground truth becomes visible only after a clarification already exists and may answer only representable questions. Pre-HITL output remains unchanged.

Real runs reject demo or unconfigured providers.

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_benchmark `
  --manifest evals/private/manifest.json `
  --split development `
  --output evals/reports/dev_run
```

Each new output directory contains machine-readable case, metric, error, and configuration artifacts; existing outputs are never overwritten. Freeze configuration only after development work is complete. A genuine final holdout must use previously unseen cases and reject configuration drift.

## Metrics

Metrics are stage-specific and retain numerator/denominator or label count.

- Recognition: precision / recall / F1, misses, hallucinations, preparation where eligible.
- Retrieval: Recall@1/@3/@5 only for verified/mappable truth.
- Selector: accuracy/coverage/abstention only when the expected candidate is retrievable.
- Portion/nutrition: MAE, interval coverage, MAPE where defined, meal error bands.
- Selective safety: unsafe auto-accept and auto-accept coverage.
- HITL: clarification rate, question burden, representable/oracle completion.
- Infrastructure: latency, provider failures, token usage where available.
- Hidden ingredients: exact identity metrics are separate from weaker risk-surfacing metrics and question false-positive burden.

Ground truth is never provided to the production stages being graded.

## Current Nutrition5k secondary dataset status

A fixed public secondary subset is checked in under `evals/public/nutrition5k/`: 12 licensed rig-captured dishes with published measured portions and reviewed visible/canonical truth.

`nutrition5k-public-secondary-v1` used nine development and three secondary holdout IDs. Those results were observed before the evaluation truth semantics were corrected.

`nutrition5k-public-secondary-v2` preserves the same IDs while versioning the corrected truth contract and portable split lock. **The three v2 secondary holdout IDs are historical cases inherited from v1 and must not be described as a new untouched holdout.** They are retained for historical comparison only. A future final holdout requires previously unseen cases.

The v2 public subset contains:

- 12 total dishes: 9 development / 3 historical holdout IDs;
- 34 visible item labels;
- 30 independently reviewed USDA mappings;
- 4 `UNMAPPABLE` visible items;
- 13 recorded hidden ingredients with v2 hidden-truth semantics.

See `docs/measured-evaluation.md` for measured aggregates, controlled ablations, limitations, and the corrected provenance boundary.

## Frozen recognition for downstream ablations

For development-only retrieval/selector experiments, capture recognition once and replay it so upstream vision sampling is identical across variants.

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_recognition_benchmark `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --output evals\reports\dev_recognition_freeze.json `
  --write-fixture evals\private\frozen\nutrition5k_v2_dev_recognition.json
```

Then replay with `--frozen-recognition`. The fixture writer refuses overwrite and binds observations to source-image SHA-256. Do not regenerate the fixture during the same experiment series, do not use frozen recognition to test an upstream prompt change, and never use the development fixture as a holdout substitute.

See [`FROZEN_RECOGNITION.md`](FROZEN_RECOGNITION.md).

## Vision prompt experiments

Prompt changes require live vision calls because the prompt itself is the intervention. Predeclare a directional screen, run only on development cases, preserve the report, and reject candidates that fail the screen rather than tuning repeatedly on the same images.

The `meal_recognition_v3_experimental` candidate is retained as a rejected experiment: it reduced some hallucinations but materially reduced recall/F1 across all three paired repeats. Production remains `meal_recognition_v2`.

See [`VISION_PROMPT_ABLATION.md`](VISION_PROMPT_ABLATION.md).

## Hidden ingredient metrics

Exact invisible-ingredient name recall and hidden-risk surfacing answer different questions and must not be conflated. Always report false-positive/question burden beside risk coverage, and distinguish initial `HYBRID_AUTO` question state from oracle-progressed staged reachability.

See [`HIDDEN_RISK_METRICS.md`](HIDDEN_RISK_METRICS.md).

## SNAPMe phone-photo recognition

The USDA SNAPMe intake is used only for visible-food recognition evidence. One before-photo per participant was selected deterministically: 30 development and 10 participant-disjoint holdout cases. Diary-only details that are not visually verifiable are excluded before scoring.

The recognition-only runner deliberately stops before USDA retrieval/canonicalization. SNAPMe amounts and nutrients are dietary-record outputs rather than weighed truth, so this dataset must not be used to claim portion or end-to-end nutrition accuracy.

Current public aggregate reports:

- `evals/reports/snapme_recognition_development.json`
- `evals/reports/snapme_recognition_holdout.json`

Raw photos and sign-off artifacts remain private/ignored.

## Guardrails

- Never mutate a published truth artifact in place; create a new dataset/evaluation-contract version.
- Never add benchmark-specific aliases or acceptable FDC IDs after inspecting model outcomes.
- Never regenerate a frozen recognition fixture mid-ablation.
- Never tune against an already-inspected holdout and then keep calling it untouched.
- Candidate unavailability is a retrieval failure, not a selector failure.
- Risk-surface coverage is not exact hidden-ingredient recall.
- Exact-ID selector sensitivity may include semantically near-equivalent USDA records; do not overstate it as product harm without adjudication.
- Cost is omitted unless a reliable versioned pricing configuration is available.

Fine-tuning is not justified before systematic errors are measured on enough separated product data and prompt/retrieval improvements have plateaued.
