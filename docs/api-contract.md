# P2 API contract with P3 grounding behavior

All meal endpoints use `/api/v1`, JSON except image upload, bearer authentication, and the error
envelope documented below. The development bearer seam deterministically maps `dev-*` tokens to a
UUID; production must replace it with verified Supabase JWT claims.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Runtime status plus provider mode and configured provider names |
| `POST` | `/api/v1/meals` | Create a meal; 201 new, 200 idempotent replay |
| `GET` | `/api/v1/meals` | Stable owned list with `date`, `limit`, `cursor` |
| `GET` | `/api/v1/meals/{meal_id}` | Review/detail representation |
| `POST` | `/api/v1/meals/{meal_id}/image` | Validated multipart image attachment |
| `POST` | `/api/v1/meals/{meal_id}/analysis` | Idempotent analysis state action |
| `PATCH` | `/api/v1/meals/{meal_id}/items/{item_id}` | Candidate, portion, preparation correction |
| `DELETE` | `/api/v1/meals/{meal_id}/items/{item_id}` | Logical removal preserving prediction evidence |
| `POST` | `/api/v1/meals/{meal_id}/items` | Record a missing item pending canonical grounding |
| `POST` | `/api/v1/meals/{meal_id}/items/{item_id}/replacement` | Atomically replace an unresolved identity and preserve its audit |
| `POST` | `/api/v1/meals/{meal_id}/clarifications/{clarification_id}/answer` | Validated answer |
| `POST` | `/api/v1/meals/{meal_id}/confirm` | Deterministic confirmation |
| `DELETE` | `/api/v1/meals/{meal_id}` | Delete aggregate and private image |
| `GET` | `/api/v1/daily-summary` | Confirmed totals for explicit `date` and IANA `timezone` |
| `POST` | `/api/v1/dev/fixtures/review-meal` | Local/test-only deterministic review fixture |
| `POST` | `/api/v1/dev/fixtures/canonical-review-meal` | Local/test-only canonical ambiguity fixture |

P3/P4 do not add public vendor proxy endpoints. OpenAI and USDA credentials and raw responses remain
server-side.
For `PATCH .../items/{item_id}` with `candidate_rank`, the application verifies the rank against the
stored candidate set, fetches USDA details through `NutritionProvider`, stores the returned per-100g
snapshot and retrieval time, then recalculates the item. User-added text similarly triggers candidate
retrieval; it cannot directly supply calories. Candidate representations include a concise
`display_name` assembled from sanitized data type, brand, and serving metadata so distinct choices do
not render as identical buttons.

Manual identity recovery accepts only a replacement query and explicit grams. It mutates the same
item, records `food_replacement`, supersedes pending item clarifications, reruns constrained
canonicalization, and creates a new blocker if the replacement still cannot be grounded. It never
silently appends a duplicate item.

## State behavior

`POST .../analysis` transitions `UPLOADED` and `FAILED_RETRYABLE` to `ANALYZING`. Replays while
`ANALYZING` return the current state. `NEEDS_REVIEW` also returns its current result. `CONFIRMED` and
`FAILED_PERMANENT` return `INVALID_MEAL_STATE`. P2 does not run recognition, so ordinary meals remain
`ANALYZING`; the deterministic fixture supplies review data without a live AI dependency.

## Error envelope

```json
{
  "error": {
    "code": "MEAL_NOT_FOUND",
    "message": "Meal was not found.",
    "request_id": "uuid",
    "details": null
  }
}
```

Stable codes include `INVALID_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `MEAL_NOT_FOUND`,
`ITEM_NOT_FOUND`, `INVALID_MEAL_STATE`, `UNSUPPORTED_IMAGE`, `IMAGE_TOO_LARGE`, `ANALYSIS_FAILED`,
`ANALYSIS_TEMPORARILY_UNAVAILABLE`, `UNRESOLVED_CLARIFICATIONS`,
`CANONICAL_FOOD_NOT_FOUND`, `CLARIFICATION_ALREADY_ANSWERED`, and `RATE_LIMITED`.

USDA failures are sanitized into stable server-side categories such as `USDA_TIMEOUT`,
`USDA_RATE_LIMITED`, `USDA_UNAVAILABLE`, `USDA_INVALID_RESPONSE`,
`USDA_AUTHENTICATION_FAILED`, and `USDA_INCOMPLETE_NUTRITION`. Raw URLs, API keys, and provider
response bodies are not returned.

AI nutrition failures are sanitized the same way, into categories such as
`AI_NUTRITION_CONFIGURATION`, `AI_NUTRITION_TIMEOUT`, `AI_NUTRITION_RATE_LIMITED`,
`AI_NUTRITION_UNAVAILABLE`, and `AI_NUTRITION_INVALID_RESPONSE`. Raw prompts, API keys, and model
response bodies are not returned.

`GET /health` returns `status`, `mode`, and a `providers` object. `mode` is `demo`, `live`, or
`unconfigured`; it is derived from the selected adapters and whether their required credentials are
present. It does not expose credentials or imply that a provider request has succeeded.

## P4/P5 analysis behavior

`POST /api/v1/meals/{meal_id}/analysis` reads the validated image, invokes `VisionProvider`, retrieves
bounded USDA candidate sets, and invokes the separate constrained selector once per active item. A
valid SELECT detail-fetches the server-owned FDC record and stores its snapshot. ABSTAIN or zero results
preserve candidates and leave canonical fields null. The response then remains `NEEDS_REVIEW`.

Neither AI stage creates calories or macros. P5 snapshots come only from `NutritionProvider.get_food`.
P4 portion estimates remain ranges; P5 does not set confirmed grams, final item nutrition, or numeric
canonical confidence.

Successful recognition is never rerun on a repeated endpoint call. Grounded items and successful
ABSTAIN decisions are also skipped. A failed canonicalization attempt may retry without discarding the
recognition run or candidate set. Canonicalizer failure degrades to a reviewable unresolved item rather
than failing the entire meal. Each AI attempt records request ID, provider, exact model, prompt version,
configuration, latency, actual token usage when present, retry count, status, and validated output.
Stable failure codes include `VISION_TIMEOUT`, `VISION_RATE_LIMITED`,
`VISION_UNAVAILABLE`, `VISION_REFUSED`, `VISION_INVALID_RESPONSE`,
`VISION_UNSUPPORTED_IMAGE`, `VISION_CONFIGURATION_ERROR`, `CANONICALIZATION_TIMEOUT`,
`CANONICALIZATION_RATE_LIMITED`, `CANONICALIZATION_UNAVAILABLE`,
`CANONICALIZATION_REFUSED`, `CANONICALIZATION_INVALID_RESPONSE`, and
`CANONICALIZATION_INVALID_SELECTION`.

Manual `candidate_rank` correction remains authoritative and performs a fresh detail lookup. Its
append-only correction records preserve the prior AI-selected rank and the user's replacement.

## P6 review behavior

After P5, P6 either resolves a safe portion to the deterministic midpoint or creates a blocking
clarification. `portion.resolution_source` is one of `AUTO_ESTIMATE`, `USER`, or
`USER_HOUSEHOLD_UNIT`. Each item also exposes a derived bounded `review_status`; clarification objects
expose `blocking` and `resolution_satisfied`. Internal policy thresholds are not returned.

Canonical choices contain only persisted candidate ranks. Portion and household choices resolve
through the stored structured `value`; the server never parses labels or trusts client-supplied grams
for a predefined option. Custom grams are accepted only for `PORTION`. Replaying an identical answer
is a no-op. A different answer to an answered clarification returns
`409 CLARIFICATION_ALREADY_ANSWERED`; subsequent changes use the item correction endpoint.

Ordinary item updates, additions, and manual replacements require finite positive grams. The explicit
zero-gram clarification option is different: it means the item is absent, marks it removed, clears
its confirmed portion and nutrition, and preserves both the portion answer and removal in the audit.

Confirmation requires canonical identity, nutrition snapshot, resolved grams with provenance, final
nutrition, and no unresolved blocking clarification for every non-removed item. It performs no AI or
provider call.

The P7 mobile client uses this contract directly. It sends only stored clarification `option_id` values
or explicit custom grams, refreshes meal state from mutation responses, and maps stable errors to user
copy. It never displays FDC IDs, raw reason codes, match quality, provider failures, or nullable numeric
confidence.

## Timezone policy

`logged_at` must include an offset and is stored in UTC. List filtering currently uses the UTC date.
Daily summary requires an explicit IANA timezone (default `UTC`) and converts each timestamp before
date comparison. A later authenticated profile preference can replace the query default.
