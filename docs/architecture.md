# Architecture

## Components

```text
Mobile App
    ↓ HTTP + X-Request-ID
FastAPI Backend
    ↓
Application Services
   ↙          ↓          ↘
Vision     Nutrition   Persistence
Provider   Provider    Repository
```

The Expo client owns presentation and input state. All vendor credentials remain server-side. A
typed service module is the only place mobile code makes backend requests.

P7 preserves a small route-state navigation shell:

```text
Today → Capture → Analysis → Review → Confirm → Detail
```

The mobile API client mirrors the FastAPI response contract with discriminated clarification unions.
It does not derive nutrition, confidence, clarification ordering, or household conversions. Every
mutation replaces screen state from the backend response. A meal attempt retains one request UUID and
meal ID across safe retries.

FastAPI owns transport concerns: schema validation, correlation IDs, stable error envelopes, and
access logs. Route handlers delegate business work to application services. The application layer
orchestrates domain objects through protocols; it does not import Supabase or external SDK objects.

The domain layer owns valid meal-state transitions, nutrition value validation, deterministic
portion arithmetic, and the structured uncertainty policy. AI prompts cannot override these rules.

P4 adds a separate visual-observation path:

```text
                     Meal Image
                         │
                         ▼
                 ┌───────────────┐
                 │ VisionProvider│
                 └───────┬───────┘
                         │
                         ▼
                 OpenAI Responses
                         │
                         ▼
                Structured Output
                         │
                         ▼
                  MealObservation
                         │
              ┌──────────┴───────────┐
              ▼                      ▼
         ObservedFood[]       Hidden uncertainty
              │
              ▼
       P3 USDA retrieval
              │
              ▼
       P5 rank-only selector
```

The image is loaded through private storage and sent as bytes encoded for the provider request; no
public bucket URL is required. The vision adapter returns only the strict application schema. It has
no nutrition provider or database tools. A separate higher-level application pipeline invokes P3 and
P5 only after recognition has produced and persisted independently measurable observations.

Infrastructure contains typed configuration and replaceable local adapters. P2 defines an
authoritative PostgreSQL/Supabase migration while the runtime remains in-memory, allowing all contract
tests to run without production credentials.

P3 implements the nutrition port with USDA FoodData Central. USDA JSON and HTTP semantics stop at the
provider boundary; application and domain code receive only canonical candidates and foods.

```text
                    ┌───────────────────┐
                    │ NutritionProvider │
                    └─────────┬─────────┘
                              │
                  ┌───────────▼───────────┐
                  │ USDA FoodData Central │
                  └───────────┬───────────┘
                              │
               search         │        details
                 │            │           │
                 ▼            │           ▼
       CanonicalFoodCandidate │    CanonicalFood
                 │            │           │
                 └────────────┴───────────┘
                              │
                              ▼
                    Nutrition snapshot
```

`FoodGroundingService` preserves ranked candidate audit records and performs the authoritative detail
lookup when a candidate is selected. Search-result nutrition can inform review, but it never becomes
the final snapshot without detail retrieval.

`NutritionProvider` now has three implementations selected by `NUTRITION_PROVIDER`: `demo`, `usda`
(FoodData Central), and `ai` (`AINutritionProvider`, source `AI_ESTIMATE`). The AI provider samples
the model several times per food, takes the per-field median, and turns calorie-sample disagreement into
a confidence value instead of external provenance. That confidence value is recorded in the candidate's
audit record only; it does not currently gate review or auto-accept. All three satisfy the same
two-method protocol, so they are interchangeable at the seam above without caller changes — but they are
not equally verified. On the AI path, `search_foods` returns exactly one candidate whose name is the
query itself, and `get_food` is a cache read of the object that same call already produced, not an
independent detail lookup. Because the candidate's name is self-referential, the SELECT-or-ABSTAIN
deterministic gate below always sees perfect identity overlap and passes unconditionally: canonical
selection and the detail-retrieval step carry no independent verification on this path, and the
`FOOD_IDENTITY` clarification layer does not engage.

`MealRecognitionService` owns recognition and its AI run. `MealCanonicalizationService` separately
retrieves candidates and makes one bounded selector call per active item. `MealContractService` keeps
the public operation unified. Successful observations, selector decisions, and candidate sets are
independently auditable; normal endpoint retries skip completed stages.

```text
P4 ObservedFood
       │
       ▼
P3 USDA search → ranks 1–5
       │
       ▼
P5 CanonicalizationProvider
       │
   ┌───┴────┐
   ▼        ▼
 SELECT   ABSTAIN
   │        │
verify     preserve candidates
rank       canonical = null
   │
   ▼
USDA details → trusted nutrition snapshot
       │
       ▼
P6 Deterministic uncertainty engine
       │
   ┌───┴────────────────┐
   ▼                    ▼
bounded calorie      material/unresolved
impact               uncertainty
   │                    │
midpoint +           deterministic
AUTO_ESTIMATE        clarification
                        │
                    user answer
                        │
              deterministic recalculation
```

The selector never receives server-side FDC IDs or nutrition. It returns only SELECT with a supplied
rank or ABSTAIN. The server validates ranks again before detail lookup. Raw model match quality remains
categorical audit data and never populates `canonical_confidence`.

`MealReviewService` applies the pure uncertainty policy after P5. The policy uses categorical P4
certainty, grounded state, hidden-ingredient impact, and Decimal min/max nutrition. It does not call a
model and its `LOW`/`MEDIUM`/`HIGH` output is a decision category—not a correctness probability.
Clarification stable keys make generation replay-safe; answer values come from persisted structured
options. Identity is resolved before hidden ingredients, and hidden ingredients before portions, so
questions do not become stale when upstream state changes.

## Evaluation boundary

P8 remains outside production business logic. `evals/run_benchmark.py` composes the existing services
with real OpenAI and USDA providers and rejects demo/unconfigured adapters. Ground truth is loaded by
the grader and is never passed to recognition, retrieval, selection, or clarification generation.

```text
private image ──► production P4/P3/P5/P6 ──► PRE_HITL_RESULT
      │                         │
      │                         └──► BASELINE_TOP1 from shared P4/P3 evidence
      │
private labels ──► stage grader ──► metrics + error attribution
      │
      └── after questions exist ──► oracle answers ──► POST_ORACLE_HITL_RESULT
```

The automatic snapshot is serialized before oracle access. The oracle can only select a generated
option or provide true grams for an already-generated portion question; it cannot influence upstream
outputs. Each run writes immutable machine-readable case, metric, error, and configuration artifacts.
Holdout execution requires a configuration file frozen during development. Private images remain
under the Git-ignored `evals/private/` boundary.

## Why a modular monolith

The seven-day deadline rewards clear boundaries without distributed-system overhead. A modular
monolith is easier to run locally, test transactionally, and observe as one process. It avoids
premature deployment, network, and consistency complexity. Provider and repository protocols leave
an extraction seam if scale or team ownership later justifies separate services.

## Request lifecycle

Every request receives a UUID. A valid `X-Request-ID` is preserved; an invalid or missing value is
replaced. The ID is placed in `request.state`, returned as a response header, included in structured
access logs, and embedded in the consistent error envelope.

## Configuration and trust boundaries

`Settings` loads typed values from process environment or `backend/.env`. Local and test modes allow
missing vendor credentials. Production startup validates required database, Supabase, and OpenAI
configuration always, and USDA configuration only when `NUTRITION_PROVIDER=usda`; it fails with the
missing variable names. `demo` is rejected in production; `usda` and `ai` are both accepted. Secret
values use `SecretStr` and are never returned to mobile.

Images, free text, request headers, provider responses, and future LLM output are untrusted. USDA
responses receive typed validation, allowlisted metadata, nutrient-unit validation, and explicit
failure mapping. AI output additionally uses `extra=forbid`; image/user context are explicitly treated
as untrusted evidence. Verified authentication and the Postgres repository adapter remain deferred.

## Repository-state note

The experimental P1 domain and service implementation has been removed. `/api/v1`, the P2 entities,
and the P2 migration are authoritative. Runtime food candidate persistence still uses the in-memory
aggregate; the production schema already includes `food_candidates`.
