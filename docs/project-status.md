# Project status and owner inputs

Status date: 2026-08-18.

This is a public, time-boxed engineering case study. The repository is runnable in deterministic demo
mode and contains live provider adapters, but it is not deployed or clinically validated. A small
public Nutrition5k secondary benchmark and a licensed SNAPMe phone-photo development recognition run
are measured; product-specific owned-capture accuracy is not.

## Implemented and verified

- Native Expo flow: Today → Capture → Analysis → Review → Confirm → Meal Detail. The complete flow
  was exercised on an Android SDK emulator on 2026-08-18 with an actual image file and the
  deterministic demo providers; the confirmed 524 kcal meal appeared in Today.
- FastAPI contract with meal ownership checks, lifecycle transitions, idempotent create semantics,
  stable errors, correlation IDs, and deterministic nutrition arithmetic.
- Strict multimodal observation schema and bounded OpenAI vision adapter.
- USDA retrieval/detail adapter with normalization, ranking, response validation, retry mapping, and
  canonical nutrition snapshots.
- Rank-constrained OpenAI selector that cannot invent an FDC ID or use nutrition as hidden selection
  evidence.
- Deterministic uncertainty policy and blocking identity, hidden-ingredient, and portion clarification.
- PostgreSQL/Supabase migrations including RLS policies.
- Private real-world dataset schema, baseline/hybrid/oracle benchmark modes, stage metrics, immutable
  report artifacts, error attribution, provider gates, and holdout configuration checks.
- Automated backend, evaluation, and mobile tests.
- Licensed 12-dish Nutrition5k secondary subset, frozen split, real-provider development iteration,
  threshold simulation, and one untouched three-dish holdout run.
- Licensed SNAPMe intake builder, independent visible-label sign-off workflow, recognition-only
  manifest promotion, and a 30-case development run with zero vision infrastructure failures.

## Implemented but not product-validated here

- `OpenAIVisionProvider`, `OpenAICanonicalizationProvider`, and
  `USDAFoodDataCentralProvider` passed smoke tests and the public secondary benchmark, but external
  availability and output remain nondeterministic.
- The real-provider benchmark requires owned/consented photos and independently measured labels under
  `evals/private/`. This directory is intentionally absent from the public repository.
- The 100 kcal / 20% auto-accept thresholds survived a seven-item conditional development simulation,
  but are not calibrated for a product population.

## Exploratory QA status

An Android emulator pass with real OpenAI/USDA providers on 2026-08-18 found five P1 workflow issues.
The current recommendation is no-go for a polished live-provider demonstration until those findings
are fixed. See [`docs/exploratory-qa-2026-08-18.md`](exploratory-qa-2026-08-18.md) for reproduction
steps, passed checks, limitations, and fix order. This does not invalidate the automated test results;
it identifies integration and state combinations that the current suite does not cover.

## Explicitly deferred

- Runtime PostgreSQL/Supabase repository and object-storage adapters; the current runtime uses memory.
- Production Supabase JWT verification; local development tokens are fixtures.
- Deployment, monitoring backend integration, operational backups, and incident response.
- Product-specific owned/consented phone-photo collection and benchmark.
- Barcode/OCR, multi-angle capture, personalized retrieval, and learning from corrections.

## Evidence status

The public secondary dataset contains 12 Nutrition5k dishes: nine development and three holdout, all
with measured portions. It has 34 visible item labels, 30 reviewed USDA mappings, and four items marked
`UNMAPPABLE`. On the three-meal holdout, food F1 was 0.353 (n=9 labels), USDA Recall@5 was 0.333
(n=3), hybrid auto-accept coverage was 0%, and every meal required clarification. See
`docs/measured-evaluation.md` for denominators and limitations. No numerical comparison with EatBetter
is claimed.

The private licensed SNAPMe subset contains 30 human-reviewed development phone photos with 77 visible
labels plus 10 independently reviewed participant-disjoint holdout photos with 36 visible labels. The development-only strict
lexical recognition result was precision 0.225 (71 predictions), recall 0.208 (77 labels), and F1
0.216. Completed one-to-one human semantic adjudication produced precision 0.845, recall 0.779, and
F1 0.811 (60 true positives, 11 false positives, 17 misses), with zero vision infrastructure
failures. The frozen holdout run completed 10/10 cases with strict lexical precision 0.382, recall
0.361, and F1 0.371. Completed one-to-one adjudication produced semantic precision 0.853, recall
0.806, and F1 0.829 (29 true positives, 5 false positives, 7 misses). It does not measure
portion, nutrition, hidden ingredients, USDA grounding, canonical selection, preparation, or
owned-product captures. Aggregate results are in `evals/reports/snapme_recognition_development.json`
and `evals/reports/snapme_recognition_holdout.json`.

## What the repository owner must provide

These inputs must remain local and must never be committed:

1. Owned or explicitly consented phone meal photos plus the private manifest.
2. Kitchen-scale portion measurements and defensible oil/sauce measurement methods.
3. Independently inspected USDA labels marked `VERIFIED`, or `UNMAPPABLE` where no defensible match
   exists.
4. A Supabase project and secrets if persistent runtime/deployment work is pursued.

After private inputs exist, follow `evals/README.md` and create a new split lock. Do not tune the
already-inspected public holdout or present it as product validation.

The final app/API emulator demonstration is complete. For submission, the owner must still record the
Loom walkthrough and paste its URL into `docs/EMAIL_SUMMARY.md`.
