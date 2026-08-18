# USDA canonical food grounding

## Why USDA

FoodData Central is the authoritative nutrition source for this phase. The LLM does not create or
modify calories or macros. External JSON is validated and converted at the nutrition-provider
boundary before application or domain code can use it.

## Retrieval flow

```text
Observed or user-entered food
→ deterministic normalized query
→ USDA /foods/search
→ sanitized ranked CanonicalFoodCandidate set
→ constrained selection (user now, model later)
→ USDA /food/{fdcId}
→ validated CanonicalFood
→ immutable per-100g snapshot on MealItem
```

Candidate ranks are contiguous and preserved for audit and future Recall@1/3/5 evaluation. Selection
must reference that retrieved set. The final snapshot always comes from detail retrieval, even when a
search response also contains complete nutrients.

## Data-type strategy

Generic meal-photo queries favor Survey (FNDDS), Foundation, and SR Legacy data. Branded records stay
eligible but receive an isolated deterministic penalty, including a brand-owner penalty, so packaged
products do not dominate searches such as cooked rice. USDA relevance, normalized token overlap,
preparation overlap, and data type are the only ranking factors. A future barcode workflow can use a
separate strategy that prefers Branded foods.

## Nutrition and energy policy

The centralized parser uses nutrient IDs: protein `1003`, total fat `1004`, carbohydrate `1005`, and
energy. Energy precedence is `2048`, then `2047`, then legacy/general `1008`; values are never averaged.
Compatible kcal values are used directly and kJ values are divided by exactly `4.184`. Macro units are
validated and safely converted from g, mg, or µg. All authoritative values use `Decimal`.

Missing nutrition is not zero. An explicitly reported zero is valid, but a missing or incompatible
required value leaves search-candidate nutrition absent. If details remain incomplete, grounding fails
with `USDA_INCOMPLETE_NUTRITION` rather than creating a misleading snapshot.

## Reliability and security

Calls use one reusable async client with an explicit timeout and at most three attempts by default.
Only timeouts, connection failures, 429, 502, 503, and 504 retry. Numeric `Retry-After` is honored up
to ten seconds; other transient failures use bounded exponential delay plus jitter. Authentication,
other client errors, invalid JSON, and invalid schemas do not retry. Detail 404 returns no food.

Rate-limit limit/remaining headers are captured for logs but never enter domain data. Structured logs
contain the provider, operation, category, latency, result count, normalized query or FDC ID, and rate
remaining when present. They never contain the API key, raw secret-bearing URL, or provider body.
Normalized food queries can still be user-derived and should receive the same retention controls as
other application logs.

## Local and production operation

Local/test defaults use the deterministic demo adapter, explicitly labeled `TEST/DEMO DATA — NOT USDA
RESULTS`. Select USDA with `NUTRITION_PROVIDER=usda`; without `USDA_API_KEY`, USDA operations fail with
a configuration error while the app can still boot. Production requires the USDA provider and key.
The default tests use sanitized fixtures and a mock HTTP transport, never the network.

Runtime persistence remains in memory in this phase. Candidate audit data lives on the aggregate, and
the existing PostgreSQL schema already provides `food_candidates` for the later repository adapter.
