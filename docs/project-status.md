# Project status and owner inputs

Status date: 2026-08-18.

This is a public, time-boxed engineering case study. The repository is runnable in deterministic demo
mode and contains live provider adapters, but it is not deployed, clinically validated, or supported by
a real-world accuracy result.

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

## Implemented but not live-validated here

- `OpenAIVisionProvider`, `OpenAICanonicalizationProvider`, and
  `USDAFoodDataCentralProvider` require private keys and external network calls.
- The real-provider benchmark requires owned/consented photos and independently measured labels under
  `evals/private/`. This directory is intentionally absent from the public repository.
- The initial 100 kcal / 20% auto-accept thresholds are hypotheses. They have not been calibrated.

## Explicitly deferred

- Runtime PostgreSQL/Supabase repository and object-storage adapters; the current runtime uses memory.
- Production Supabase JWT verification; local development tokens are fixtures.
- Deployment, monitoring backend integration, operational backups, and incident response.
- Real-world development iteration, frozen final configuration, and untouched holdout benchmark.
- Barcode/OCR, multi-angle capture, personalized retrieval, and learning from corrections.

## Evidence status

The public dataset count is 0: 0 development, 0 holdout, 0 measured portions, and 0 manually verified
FDC labels. `BASELINE_TOP1`, `HYBRID_AUTO`, and `HYBRID_ORACLE_HITL` therefore remain **Not measured**.
This is an evidence blocker, not an accuracy score. No numerical comparison with EatBetter is claimed.

## What the repository owner must provide

These inputs must remain local and must never be committed:

1. An OpenAI API key authorized for the configured vision and canonicalization models.
2. A USDA FoodData Central API key.
3. Owned or explicitly consented meal photos plus the private manifest.
4. Kitchen-scale portion measurements and defensible oil/sauce measurement methods.
5. Independently inspected USDA labels marked `VERIFIED`, or `UNMAPPABLE` where no defensible match
   exists.
6. A Supabase project and secrets if persistent runtime/deployment work is pursued.

After those inputs exist, follow `evals/README.md`: validate and lock the split, smoke-test live
providers, run development baseline/hybrid/oracle, make exactly one evidence-based iteration, simulate
thresholds, freeze configuration, and run holdout once. README results should only be replaced after
those artifacts exist.

For submission, the owner must also record the Loom walkthrough, replace the placeholder signature in
`docs/EMAIL_SUMMARY.md`, and decide where the app/API will be demonstrated.
