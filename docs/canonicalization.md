# Constrained canonicalization

## Why constrained selection

P4 has already answered “what food appears visible?” P5 asks a narrower question: given this observation
and only these USDA candidates, should the system SELECT one supplied rank or ABSTAIN? The model cannot
create a canonical food record. A materially wrong automatic match is worse than an explicit unresolved
item, so abstention is a successful safety outcome.

## Pipeline

```text
P4 ObservedFood
→ preparation-aware normalized query
→ P3 USDA top-five candidate set
→ P5 constrained selector
→ SELECT supplied rank or ABSTAIN

SELECT → server rank validation → USDA detail → trusted snapshot
ABSTAIN → preserve candidates → canonical fields remain null
```

Zero candidates deterministically abstains without an LLM call. Removed or already grounded items are
skipped. Successful selection and abstention are idempotent. Failed item-level selector calls may retry
without rerunning vision, erasing candidates, or making the recognized meal unusable.

## Query composition

`build_grounding_query` combines the observed food with allowlisted meaningful preparation terms such
as raw, cooked, fried, grilled, roasted, steamed, boiled, baked, skinless, and with-skin. It normalizes
case and punctuation and avoids adding terms already present. Arbitrary preparation prose is not sent
to USDA search.

## Model boundary

The text-only `CanonicalizationProvider` is independent of `VisionProvider`. The OpenAI adapter uses
the Responses API and strict `CanonicalizationOutput` with:

- decision: `SELECT` or `ABSTAIN`;
- selected rank: required only for SELECT;
- match quality: `EXACT`, `STRONG`, `AMBIGUOUS`, or `NO_MATCH`;
- at most five bounded reason codes.

The model sees rank, description, data type, optional brand owner, and optional household serving text.
It does not see FDC IDs, candidate nutrition, arbitrary provider metadata, or search-result payloads.
Observation text, context, and candidate metadata are explicitly untrusted. The server validates the
selected rank against the exact supplied set even after structured-output validation; invalid ranks
never become abstention or rank-one fallback.

Match quality is diagnostic, not a probability. P5 never writes `canonical_confidence`; P6 will define
measurable system-confidence and uncertainty policy. P5 also does not confirm portions or create final
nutrition totals.

## Audit and human override

Every selector call uses AI-run stage `CANONICALIZATION` and records meal-item ID, decision, rank, match
quality, reason codes, provider, exact model, prompt version, reasoning effort, latency, actual usage,
retry count, status, and stable error code. Candidate records remain on the item. A later manual PATCH
detail-grounds the user's selected rank and appends a correction without changing the historical AI run.

## Failure and retry policy

The OpenAI SDK's retries remain disabled. The adapter retries timeouts, connection failures, 429, and
temporary 5xx responses with at most three attempts by default. Refusal, schema errors, invalid ranks,
and logical ABSTAIN do not retry. A provider failure differs from abstention and is recorded as FAILED;
the meal remains reviewable with its observation and retrieved candidates.

## Evaluation

Selector evaluation uses frozen candidate sets so USDA search changes do not invalidate it. Retrieval
Recall@1/3/5 remains separate. The selector report compares constrained selection to a `USDA_TOP_1`
baseline and exposes coverage alongside accuracy so constant abstention cannot look deceptively safe.
All checked-in cases remain unverified and all metrics null until FDC truth is manually established.
