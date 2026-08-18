# EatBetter — confidence-aware AI meal logger

## Goal and thesis

Build a mobile meal logger that minimizes confidently wrong nutrition entries. AI will produce
observations and uncertainty; canonical retrieval, deterministic nutrition, and human review remain
authoritative.

This repository is a time-boxed full-stack case study, not a production nutrition or medical product.
It demonstrates the architecture, native workflow, safety policy, provider boundaries, and evaluation
harness. It includes a small measured public secondary benchmark and a licensed external phone-photo
development benchmark, but not product-specific owned-capture accuracy evidence.

## Current state — P8.5 measured evidence complete on a public secondary subset

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
artifacts, error taxonomy, and holdout configuration lock. P8.5 ran those components on a licensed
12-dish Nutrition5k subset with nine development and three untouched holdout dishes. Demo fixtures were
rejected. This is secondary rig-captured evidence, not a product-specific smartphone benchmark.

| Area | Public repository status |
|---|---|
| Native Expo capture/review flow | Implemented and tested |
| FastAPI meal lifecycle | Implemented and tested with in-memory adapters |
| OpenAI vision and constrained selector adapters | Implemented; live execution requires a private key |
| USDA FoodData Central adapter | Implemented; live execution requires a private key |
| PostgreSQL/Supabase schema and RLS | Defined in migrations; runtime persistence adapter is deferred |
| Accuracy benchmark | 12 Nutrition5k dishes plus 30 human-reviewed licensed SNAPMe development photos; no phone-photo holdout result |
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
[mobile UX](docs/mobile-ux.md), [measured evaluation](docs/measured-evaluation.md),
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

## Accuracy evaluation

The measured portion/nutrition dataset is a fixed, licensed 12-dish Nutrition5k secondary subset: nine development meals
and a three-meal untouched holdout. All 12 have published measured portions; 30/34 visible item labels
have independently reviewed USDA mappings and four are explicitly `UNMAPPABLE`. Nutrition5k uses a
custom scanning rig, and the private product-specific owned-capture dataset remains at 0 cases.

On the three-meal case-study holdout, food F1 was 0.353 (9 labeled items) and USDA Recall@5 was 0.333
(3 verified recognized items). Rank-1 produced nutrition totals for two meals, with 20.177 kcal MAE,
but both accepted meals were materially wrong because required verified foods were missing or wrong.
The hybrid auto-accepted 0/3 meals, asked 1.667 blocking questions per meal, and produced no complete
nutrition totals. None of five generated questions was validly oracle-resolvable, so oracle-assisted
results equaled automatic results.

The single development iteration, `meal_recognition_v2`, raised development food F1 from 0.286 to
0.615 while holding retrieval, selection, thresholds, and labels fixed. It did not produce consistent
end-to-end nutrition improvement. See [measured evaluation](docs/measured-evaluation.md) for all
denominators, before/after results, error attribution, threshold simulation, latency, and limitations;
see [`evals/README.md`](evals/README.md) for the reproducible protocol. No clinical, production-level,
or competitor-comparison claim is made.

A separate recognition-only run used 30 licensed SNAPMe phone photos and 77 visible labels accepted by
an independent human reviewer. All 30 development cases completed. Under strict exact normalized
label matching, precision was 0.225 (n=71 predictions), recall 0.208 (n=77 labels), and F1 0.216;
there were 55 hallucinated and 61 missed labels. This is a lexical lower bound: reasonable synonyms
still count as errors unless independently approved as aliases. The 10 participant-disjoint holdout
photos remain visually unreviewed and were not run. No portion, hidden-ingredient, nutrition, USDA,
canonicalization, preparation, product-validation, or holdout claim is supported by SNAPMe.

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
across process death, OCR, barcode recognition, calibrated confidence research, and product-specific
phone-photo collection remain incomplete. Recognition, retrieval, selector, portion,
nutrition, review, clarification, and infrastructure failures remain independently attributable.
