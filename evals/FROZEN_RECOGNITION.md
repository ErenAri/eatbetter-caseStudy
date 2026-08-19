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

## Guardrails

- Frozen recognition replay is development-only. The runner rejects it for holdout.
- A frozen-recognition run cannot write `final_configuration.json`; final product configuration must be
  frozen from a normal end-to-end development run.
- Non-production ranker ablations require frozen recognition.
- Vision latency and vision token usage from replay runs are not comparable with live vision runs.
  Use frozen runs to compare downstream retrieval/selector behavior, not end-to-end cost or latency.
- Do not edit a fixture in place. Create a new fixture only when intentionally starting a new
  experiment series, and treat its fixture SHA-256 as a new upstream input version.
