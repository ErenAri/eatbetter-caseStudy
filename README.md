# EatBetter — confidence-aware AI meal logger

## Goal and thesis

Build a mobile meal logger that minimizes confidently wrong nutrition entries. AI will produce
observations and uncertainty; canonical retrieval, deterministic nutrition, and human review remain
authoritative.

This repository is a time-boxed full-stack case study, not a production nutrition or medical product.
It demonstrates the architecture, native workflow, safety policy, provider boundaries, and evaluation
harness. It does not yet contain real-world accuracy evidence.

## Current state — P8 harness complete; real benchmark blocked

The normal analysis endpoint now runs independently audited P4 recognition, P3 retrieval, P5
SELECT-or-ABSTAIN matching, USDA detail verification, and deterministic P6 uncertainty review before
returning `NEEDS_REVIEW`. P6 auto-accepts only safe portion midpoints, records resolution provenance,
and creates idempotent blocking clarifications in identity → hidden ingredient → portion order.

P7 exposes that pipeline as a native Expo flow: Today → Capture → Analysis → Review → Confirm → Meal
Detail. The interface does not expose raw model confidence. Instead, it converts uncertainty into
actionable review only when the backend determines that the uncertainty can materially affect the meal
result. Nutrition is always displayed from backend responses; the client never recalculates it.

Local/test analysis uses clearly labeled deterministic providers. OpenAI selectors receive candidate
ranks and allowlisted descriptions—not FDC IDs or nutrition. SELECT is validated server-side and then
detail-grounded; ABSTAIN preserves candidates and leaves the food unresolved.

P8 adds a strict private-dataset contract, real-provider-only benchmark runner, rank-1 baseline,
automatic hybrid snapshot, evaluation-only oracle clarification, stage metrics, immutable run
artifacts, error taxonomy, and holdout configuration lock. No real meal dataset or vendor credentials
exist in this workspace, so no accuracy number is claimed and demo fixtures are rejected by the
runner.

| Area | Public repository status |
|---|---|
| Native Expo capture/review flow | Implemented and tested |
| FastAPI meal lifecycle | Implemented and tested with in-memory adapters |
| OpenAI vision and constrained selector adapters | Implemented; live execution requires a private key |
| USDA FoodData Central adapter | Implemented; live execution requires a private key |
| PostgreSQL/Supabase schema and RLS | Defined in migrations; runtime persistence adapter is deferred |
| Real-world accuracy benchmark | Harness implemented; 0 real cases and no measured result |
| Production authentication/deployment | Not implemented |

See [project status and owner inputs](docs/project-status.md) for the exact boundary between working,
demonstrated, and deferred behavior.

## Repository structure

```text
mobile/                    Expo application and typed backend service layer
backend/app/api/           /health and /api/v1 transport contracts
backend/app/application/   meal lifecycle orchestration and stable errors
backend/app/ai/            strict observation schemas, providers, versioned prompts
backend/app/domain/        entities, Decimal nutrition, states, uncertainty
backend/app/nutrition/     USDA adapter, parsing, normalization, ranking
backend/app/repositories/  in-memory P2 repository adapter
backend/app/infrastructure typed config and private storage adapter
backend/tests/             deterministic unit/integration/contract tests
supabase/migrations/       authoritative PostgreSQL schema
docs/                      architecture, API, database workflow, ADRs
evals/                     private-data contract, benchmark runner, metrics, reports
```

See [architecture](docs/architecture.md), [project status](docs/project-status.md),
[canonicalization](docs/canonicalization.md), [vision recognition](docs/vision-recognition.md),
[USDA grounding](docs/usda-grounding.md), [API contract](docs/api-contract.md),
[uncertainty and clarification](docs/uncertainty-and-clarification.md),
[mobile UX](docs/mobile-ux.md),
[evaluation protocol](docs/evaluation.md),
[database workflow](docs/database.md), and [ADR 0001](docs/decisions/0001-modular-monolith.md).

We intentionally traded some zero-friction logging for selective confirmation. The system interrupts
only when unresolved uncertainty can materially change the logged result. A 20 g range matters far
more for oil than parsley because P6 evaluates calorie impact, not gram spread alone. The initial
100 kcal / 20% limits are configurable hypotheses, not calibrated or clinically validated thresholds.
No calibrated numeric confidence exists, so `canonical_confidence` remains null.

## API endpoints

| Method | Path |
|---|---|
| `GET` | `/health` |
| `POST`, `GET` | `/api/v1/meals` |
| `GET`, `DELETE` | `/api/v1/meals/{meal_id}` |
| `POST` | `/api/v1/meals/{meal_id}/image` |
| `POST` | `/api/v1/meals/{meal_id}/analysis` |
| `PATCH`, `DELETE` | `/api/v1/meals/{meal_id}/items/{item_id}` |
| `POST` | `/api/v1/meals/{meal_id}/items` |
| `POST` | `/api/v1/meals/{meal_id}/clarifications/{clarification_id}/answer` |
| `POST` | `/api/v1/meals/{meal_id}/confirm` |
| `GET` | `/api/v1/daily-summary?date=YYYY-MM-DD&timezone=Europe/Istanbul` |
| `POST` | `/api/v1/dev/fixtures/review-meal` (local/test only) |

Create replay semantics are deterministic: a new `(user_id, meal_request_id)` returns `201`; the same
authenticated user and request ID returns the existing resource with `200`.

## Backend setup

Prerequisites: Python 3.13 (matching the Dockerfile) and, for live analysis only, private OpenAI and
USDA credentials. Demo mode is the default and requires no external credentials.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. Local endpoints accept a development bearer
token such as `Authorization: Bearer dev-11111111-1111-4111-8111-111111111111`; production must verify
Supabase JWTs.

Run tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

To inspect live USDA candidates without exposing the API key in output:

```powershell
cd backend
$env:NUTRITION_PROVIDER = "usda"
$env:USDA_API_KEY = "your-real-key"
.\.venv\Scripts\python.exe scripts\search_usda.py "white rice cooked"
```

To run P4-only observation against a local private image (no USDA call):

```powershell
cd backend
$env:VISION_PROVIDER = "openai"
$env:OPENAI_API_KEY = "your-real-key"
.\.venv\Scripts\python.exe scripts\analyze_meal.py .\meal.jpg --context "Cooked at home"
```

## Database setup

The baseline references Supabase `auth.users` and uses RLS as defense in depth:

```powershell
npx supabase start
npx supabase db reset
```

See [database workflow](docs/database.md) before resetting or pushing a linked database.

## Mobile setup

Prerequisites: Node.js 20+ and npm. A physical phone must use the development computer's LAN address
instead of `127.0.0.1` in `mobile/.env`.

```powershell
cd mobile
Copy-Item .env.example .env
npm install
npm start
```

Verification:

```powershell
npm test
npm run typecheck
npx expo-doctor
```

## Data and privacy decisions

- Auth passwords are never stored; `profiles.id` corresponds to `auth.users.id`.
- Every repository lookup includes authenticated ownership; RLS repeats that constraint.
- Original observations, offered candidates, AI structured output, corrections, and clarification
  answers remain separately auditable.
- Confirmed items snapshot the canonical nutrition used, so history never depends on a future API call.
- Meal deletion cascades relational children and the application deletes the generated private image
  path. Original filenames are never trusted as storage keys.
- Daily summary converts `logged_at` using the explicitly requested IANA timezone; UTC is the default.

## Accuracy Evaluation

Dataset status: 0 real cases available in this workspace (0 development, 0 holdout, 0 measured
portions, 0 manually verified FDC IDs). The target remains 30–40 consented phone photos with a roughly
75/25 development/case-study-holdout split. Private images and labels belong under Git-ignored
`evals/private/`.

| Configuration | Definition | Result |
|---|---|---|
| `BASELINE_TOP1` | Shared P4/P3 evidence; rank 1; portion midpoint; no clarification | Not measured |
| `HYBRID_AUTO` | P4→P3→P5→P6 before answers | Not measured |
| `HYBRID_ORACLE_HITL` | Evaluation-only correct answers where generated options permit | Not measured |

Development and holdout results are not measured because `OPENAI_API_KEY`, `USDA_API_KEY`, and a real
private manifest are unavailable. This is an execution blocker, not a zero score. See
[`evals/README.md`](evals/README.md) for collection, independent USDA verification, privacy, commands,
metric denominators, immutable artifacts, and the holdout lock. No comparison with EatBetter or any
clinical/production accuracy claim is made.

Raw benchmark directories and private meal photos are ignored by Git. Only deliberately reviewed,
aggregate, non-sensitive reports should ever be committed to this public repository.

## Public repository safety

- Never commit `.env` files, API keys, Supabase service-role credentials, private meal photos, or raw
  benchmark case output.
- The local development bearer token is a fixture, not authentication suitable for deployment.
- Meal and nutrition output is not medical advice and has not been clinically validated.
- See [security policy](SECURITY.md) before reporting a vulnerability or sharing a private image.
- Contributions should follow [CONTRIBUTING.md](CONTRIBUTING.md).

## Deferred

Production Supabase/JWT adapters, a standalone manual food-search endpoint, persistent navigation state
across process death, OCR, barcode recognition, calibrated confidence research, and real-world data
collection/live benchmark execution remain incomplete. Recognition, retrieval, selector, portion,
nutrition, review, clarification, and infrastructure failures remain independently attributable.
