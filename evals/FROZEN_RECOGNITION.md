# Frozen recognition development ablations

Use frozen recognition only for **development-stage isolation**. The goal is to compare retrieval,
ranking, canonicalization, and clarification changes against identical upstream vision observations.
It is not a replacement for the normal end-to-end benchmark and it must not be used to tune or rerun
the holdout.

## 1. Capture the development recognition fixture once

Run the recognition-only benchmark with the same development manifest used by the meal benchmark:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_recognition_benchmark `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --output evals\reports\2026-08-19_dev_recognition_freeze.json `
  --write-fixture evals\private\frozen\nutrition5k_v2_dev_recognition.json
```

The fixture contains the full structured vision observation for every requested case, including visible
items, preparation, portion ranges, certainty, hidden-ingredient hypotheses, and meal-level
uncertainty. Each case is bound to the exact source image bytes with SHA-256. The fixture writer is
immutable and refuses overwrite; all requested recognition cases must complete before a fixture can be
written.

Do **not** regenerate the fixture between retrieval/ranking variants. Regenerating it would reintroduce
upstream model sampling into the A/B comparison.

## 2. Replay the same recognition input downstream

Use the captured fixture with the normal meal benchmark:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_benchmark `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --frozen-recognition evals\private\frozen\nutrition5k_v2_dev_recognition.json `
  --output evals\reports\2026-08-19_dev_retrieval_ablation
```

Replay validates all of the following before running:

- fixture schema version,
- dataset version,
- development split,
- exact case-id set,
- exact image SHA-256 for every case,
- structured observation schema.

`configuration.json` records `recognition_input_mode=FROZEN` and the SHA-256 of the fixture itself, so
two downstream reports can be checked for identical upstream input.

## 3. P1 ranker ablation

The production ranker remains `semantic`. For a controlled development experiment, the runner also
exposes `score-first-pr-b`, which reproduces the pre-PR-C USDA-score-first ranking formula while keeping
the current required-identity queries, loose fallback, raw pool size, and FDC-ID dedupe unchanged.

Run both variants with the **same** frozen recognition fixture:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_benchmark `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --frozen-recognition evals\private\frozen\nutrition5k_v2_dev_recognition.json `
  --retrieval-ranker semantic `
  --output evals\reports\2026-08-19_dev_ranker_semantic

.\backend\.venv\Scripts\python.exe -m evals.run_benchmark `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --frozen-recognition evals\private\frozen\nutrition5k_v2_dev_recognition.json `
  --retrieval-ranker score-first-pr-b `
  --output evals\reports\2026-08-19_dev_ranker_score_first_pr_b
```

Compare exact Recall@1/@3/@5, selector selection accuracy, selective accuracy, wrong selection,
wrong-strong selection, and the per-item candidate lists. `configuration.json` records the selected
`retrieval_ranker` and must show the same recognition fixture SHA-256 in both runs.

The score-first ranker is an ablation control, not a product configuration. The runner rejects it
without frozen recognition, so it cannot be used accidentally in a live end-to-end or holdout run.

## 4. P2 selector permutation robustness

P2 measures whether canonical selection changes merely because the same candidate identities are
presented in a different order. The runner only evaluates items whose recognition matches a ground-truth
item, whose canonical truth is `VERIFIED`, and whose acceptable FDC ID is already present in the top
five. Retrieval misses and recognition errors are therefore excluded from the selector-robustness
denominator.

Use the score-first control first because P1 showed better downstream selector safety on the frozen
development input:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_selector_permutation_eval `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --frozen-recognition evals\private\frozen\nutrition5k_v2_dev_recognition.json `
  --retrieval-ranker score-first-pr-b `
  --output evals\reports\2026-08-19_selector_permutation_score_first.json
```

Each eligible item receives seven canonicalization calls:

- `CONTROL_A`, `CONTROL_B`, `CONTROL_C`: identical candidate array and rank labels; estimates model
  stochasticity on a repeated identical request.
- `ARRAY_REVERSED`, `ARRAY_ROTATE_LEFT`: candidate array order changes while each candidate keeps its
  original numeric rank. These isolate serialization/array-position sensitivity.
- `RERANK_REVERSED`, `RERANK_ROTATE_LEFT`: candidate identities are reordered and ranks are reassigned
  `1..N`. These measure sensitivity to the production ranking/rank-label signal.

The report stores raw model selection and the post-deterministic-gate selection separately. Primary
metrics are control-repeat instability, array-position sensitivity, rank-label sensitivity, and
condition-level canonical accuracy. Interpret permutation sensitivity relative to control-repeat
instability; a difference seen equally often in repeated controls is stochasticity, not evidence of
position bias.

## 5. P4 frozen recognition segmentation diagnostics

P4 explains why the strict visible-food metric reports a miss/hallucination without changing that
metric or adding new aliases after the fact. It uses the immutable P0 recognition fixture and performs
no model calls.

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_recognition_segmentation_analysis `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --frozen-recognition evals\private\frozen\nutrition5k_v2_dev_recognition.json `
  --output evals\reports\2026-08-20_recognition_segmentation_diagnostics.json
```

The diagnostic first performs the same strict normalized exact-label/pre-approved-alias matching used
by the primary recognition metric. Only remaining mismatches are classified, using conservative lexical
containment:

- `UNDER_SEGMENTATION`: one predicted composite contains two or more independently expected foods,
  such as `bagel with cream cheese` against separate `bagel` and `cream cheese` truth labels.
- `OVER_SEGMENTATION`: multiple predicted fragments jointly cover one expected composite label.
- `IDENTITY_WITH_EXTRA_MODIFIERS`: one prediction contains one expected identity plus additional
  descriptive tokens, such as `chopped cooked chicken` against `chicken`.
- `BROADER_LABEL`: a prediction is lexically broader than the expected label.
- `UNEXPLAINED_MISS` / `UNEXPLAINED_PREDICTION`: strict mismatches not explained by the conservative
  lexical rules; these require separate semantic/image review.

The report conserves strict error units: an under-segmentation event that produces two primary misses
and one primary hallucination is recorded as one structural event carrying three strict error units.
This prevents one granularity mistake from being mistaken for three independent recognition failures
while leaving primary precision/recall/F1 unchanged.

Do not use this diagnostic taxonomy to silently approve new aliases or to claim a higher recognition
accuracy. It exists to choose the next engineering intervention: segmentation policy, naming policy, or
true visual-identity errors.

## Guardrails

- Frozen recognition replay is development-only. The runner rejects it for holdout.
- A frozen-recognition run cannot write `final_configuration.json`; final product configuration must be
  frozen from a normal end-to-end development run.
- Non-production ranker ablations require frozen recognition.
- Selector permutation evaluation is development-only and does not mutate product ranking, prompts,
  ground truth, acceptable FDC IDs, or selector thresholds.
- Recognition segmentation diagnostics are development-only and do not modify the primary strict
  recognition metric, manifest aliases, vision prompt, or frozen fixture.
- Vision latency and vision token usage from replay runs are not comparable with live vision runs.
  Use frozen runs to compare downstream retrieval/selector behavior, not end-to-end cost or latency.
- Do not edit a fixture in place. Create a new fixture only when intentionally starting a new
  experiment series, and treat its fixture SHA-256 as a new upstream input version.
