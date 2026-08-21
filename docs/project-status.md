# Project status and owner inputs

Status date: 2026-08-20.

This is a public, time-boxed engineering case study. The repository is runnable in deterministic demo mode and contains live OpenAI/USDA provider adapters, but it is not deployed or clinically validated. Product-specific owned/consented phone-capture accuracy remains unmeasured.

## Implemented and verified

- Native Expo flow: Today → Capture → Analysis → Review → Confirm → Meal Detail.
- Full image upload → analysis → clarification → confirmation flow exercised on an Android SDK emulator with deterministic demo providers.
- FastAPI contract with ownership checks, lifecycle transitions, idempotent create semantics, stable errors, correlation IDs, and deterministic nutrition arithmetic.
- Strict multimodal observation schema and bounded OpenAI vision adapter.
- USDA retrieval/detail adapter with normalization, ranking, typed validation, retry mapping, and canonical nutrition snapshots.
- Rank-constrained OpenAI selector that cannot invent an FDC ID or use nutrition as hidden selection evidence.
- Deterministic uncertainty policy and blocking identity → hidden ingredient → portion clarification ordering.
- Canonical candidate clarification now includes a direct `REMOVE_ITEM` recovery path for hallucinated candidate-bearing foods; the regression suite verifies it resolves without additional grounding/model work.
- PostgreSQL/Supabase migrations including RLS policies.
- Private real-world dataset schema, baseline/hybrid/oracle benchmark modes, stage metrics, immutable report artifacts, error attribution, provider gates, split locks, and frozen recognition fixtures.
- Standalone Android debug APK built, installed, and cold-launched on the SDK emulator during QA.
- P0 hardening blocks staging/production startup while only development authentication, in-memory repository, and in-memory storage adapters exist.
- Backend dependency audit clean after HTTP/upload stack upgrades.
- Licensed Nutrition5k secondary subset plus licensed SNAPMe phone-photo recognition evaluation.
- Automated backend, evaluation, and mobile tests; submission CI workflow added for backend/eval/mobile verification.

## Current verification

Latest locally verified state after the canonical remove-recovery change:

- Backend: **156 passed**
- Mobile: **28/28 passed** across 7 suites
- TypeScript: **clean**

The historical QA closeout keeps the test counts recorded on 2026-08-19 rather than being rewritten retroactively.

## Implemented but not product-validated here

- `OpenAIVisionProvider`, `OpenAICanonicalizationProvider`, and `USDAFoodDataCentralProvider` have real-provider benchmark/smoke-test evidence, but external availability and output remain nondeterministic.
- The real-provider product benchmark still requires owned/consented phone photos and independently measured labels under `evals/private/`.
- The 100 kcal / 20% auto-accept limits survived a seven-item conditional development simulation but are not calibrated for a product population.
- SNAPMe supports visible-food recognition evidence only; it does not validate weighed portion, hidden-ingredient, nutrition, USDA-selection, or end-to-end product accuracy.
- `AINutritionProvider` (`NUTRITION_PROVIDER=ai`) resolves nutrition from the model alone with no external database. It has unit tests but **no accuracy measurement**. Every published Nutrition5k and SNAPMe number was produced with USDA grounding under `meal_recognition_v2`; none of them describes the AI path, and none may be cited as evidence for it.
- The runtime recognition prompt is now `meal_recognition_v4`. Because `PROMPT_VERSION` is global, the shipped configuration no longer matches the benchmarked one for any provider. `meal_recognition_v2.md` is unchanged and hash-guarded against the SNAPMe configuration lock.
- The production validator now accepts `NUTRITION_PROVIDER=usda` or `ai` and requires `USDA_API_KEY` only when `usda` is selected. `demo` is still rejected and staging/production startup otherwise remains fail-closed.

## Exploratory QA status

An Android emulator pass with real OpenAI/USDA providers on 2026-08-18 found five P1 workflow issues, eight P2 issues, and one P3 issue. The scoped findings were fixed and regression-tested. Follow-up hardening covered production fail-closed startup, dependency auditing, destructive-action confirmation, and accessibility polish.

See [`exploratory-qa-2026-08-18.md`](exploratory-qa-2026-08-18.md) and [`qa-closeout-2026-08-19.md`](qa-closeout-2026-08-19.md).

## Explicitly deferred

- Runtime PostgreSQL/Supabase repository and object-storage adapters; the current runtime uses memory.
- Production Supabase JWT verification; local development tokens are fixtures.
- Staging and production startup intentionally fail closed until production adapters exist.
- Deployment, monitoring backend integration, operational backups, and incident response.
- Product-specific owned/consented phone-photo collection with weighed portions and measured oil/sauce.
- Physical-device Android lifecycle QA, iOS QA, and full screen-reader passes.
- Barcode/OCR, multi-angle capture, personalized retrieval, and learning from corrections.

## Evidence status

### Nutrition5k secondary evidence

The checked-in public secondary dataset contains 12 Nutrition5k dishes: nine development IDs and three historical secondary holdout IDs inherited from v1, all with published measured portions. It has 34 visible item labels, 30 reviewed USDA mappings, and four items marked `UNMAPPABLE`.

The corrected `nutrition5k-public-secondary-v2` contract changes evaluation truth semantics while preserving the original IDs. **The three historical holdout dishes were already observed under v1 and are not claimed as a newly untouched v2 holdout.** They remain only for historical comparison; a future final holdout requires previously unseen cases.

Historical three-dish secondary holdout results include food F1 0.353 (n=9 labels), USDA Recall@5 0.333 (n=3), hybrid auto-accept coverage 0%, and review on every meal. No numerical comparison with EatBetter is claimed.

### SNAPMe phone-photo recognition

The licensed SNAPMe subset contains 30 human-reviewed development phone photos with 77 visible labels plus 10 participant-disjoint holdout photos with 36 reviewed visible labels.

Development one-to-one semantic adjudication produced precision 0.845, recall 0.779, and F1 0.811. The frozen participant-disjoint holdout completed 10/10 cases; semantic adjudication produced precision 0.853, recall 0.806, and F1 0.829 (29 true positives, 5 false positives, 7 misses).

This remains recognition-only external evidence. SNAPMe does not support claims about portion, hidden ingredients, nutrition, USDA grounding, canonical selection, preparation, owned-product captures, clinical accuracy, or superiority to another product.

See [`measured-evaluation.md`](measured-evaluation.md) for denominators and limitations.

## What the repository owner must still provide for product validation

These inputs must remain local and must never be committed:

1. Owned or explicitly consented phone meal photos plus a private manifest.
2. Kitchen-scale portion measurements and defensible oil/sauce measurement methods.
3. Independently inspected USDA labels marked `VERIFIED`, or `UNMAPPABLE` where no defensible match exists.
4. A production Supabase project and secrets if persistent runtime/deployment work is pursued.

After private inputs exist, follow `evals/README.md` and create a new split lock. Do not tune against already-inspected secondary cases or present them as newly untouched product validation.

## Submission remaining

The application, architecture, evaluation tooling, and submission write-up are ready. The repository owner still needs to record the 5–10 minute Loom walkthrough and paste its URL into `EMAIL_SUMMARY.md` before sending the submission.
