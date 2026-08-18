# Project status and owner inputs

Status date: 2026-08-18.

This is a public, time-boxed engineering case study. The repository is runnable in deterministic demo
mode and contains live provider adapters, but it is not deployed or clinically validated. A small
public Nutrition5k secondary benchmark is measured; product-specific phone-photo accuracy is not.

## Implemented and verified

- Native Expo flow: Today → Capture → Analysis → Review → Confirm → Meal Detail.
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

## Implemented but not product-validated here

- `OpenAIVisionProvider`, `OpenAICanonicalizationProvider`, and
  `USDAFoodDataCentralProvider` passed smoke tests and the public secondary benchmark, but external
  availability and output remain nondeterministic.
- The real-provider benchmark requires owned/consented photos and independently measured labels under
  `evals/private/`. This directory is intentionally absent from the public repository.
- The 100 kcal / 20% auto-accept thresholds survived a seven-item conditional development simulation,
  but are not calibrated for a product population.

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

## What the repository owner must provide

These inputs must remain local and must never be committed:

1. Owned or explicitly consented phone meal photos plus the private manifest.
2. Kitchen-scale portion measurements and defensible oil/sauce measurement methods.
3. Independently inspected USDA labels marked `VERIFIED`, or `UNMAPPABLE` where no defensible match
   exists.
4. A Supabase project and secrets if persistent runtime/deployment work is pursued.

After private inputs exist, follow `evals/README.md` and create a new split lock. Do not tune the
already-inspected public holdout or present it as product validation.

For submission, the owner must also record the Loom walkthrough, replace the placeholder signature in
`docs/EMAIL_SUMMARY.md`, and decide where the app/API will be demonstrated.
