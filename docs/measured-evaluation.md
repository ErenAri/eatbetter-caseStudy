# Measured evaluation — public Nutrition5k secondary subset

Status date: 2026-08-18.

## Evidence boundary

This is measured evidence on a fixed 12-dish subset of Google Research's Nutrition5k dataset, not an
EatBetter product benchmark. Nine official RGB-training dishes form the development split and three
official RGB-test dishes form the untouched case-study holdout. Nutrition5k uses a custom scanning
rig, so these images do not reproduce ordinary single-phone capture. The holdout is far too small for
generalization or clinical claims.

All 12 images and published labels are licensed under CC BY 4.0. The checked-in builder records source
URLs and SHA-256 hashes. The locked dataset SHA-256 is
`99f5fd54d7d3aac353a839fb4e1499d547caa18c0f7e9843cf32b26b26539a68`.

| Dataset fact | Count |
|---|---:|
| Total / development / holdout dishes | 12 / 9 / 3 |
| Dishes with measured portions | 12 |
| Visible labeled items | 34 |
| Visible items with independently reviewed USDA mappings | 30 |
| Visible items marked `UNMAPPABLE` | 4 |
| Recorded hidden ingredients | 13 |

Category membership is overlapping: 4 simple, 8 multi-component, 7 portion-sensitive, 3 composite,
3 sauce-or-oil, and 3 hidden-ingredient dishes. The local `evals/private/` product dataset still has
0 cases; owned or consented phone photos remain necessary.

## Live configuration and gate

The runner rejected demo providers and used `OpenAIVisionProvider`,
`USDAFoodDataCentralProvider`, and `OpenAICanonicalizationProvider`. Both required keys were present
but were never printed. A pre-benchmark smoke test loaded all three production adapters, retrieved a
live USDA banana result (FDC 2709224), and completed a constrained selector call. The vision smoke test
correctly rejected a synthetic non-meal illustration as unusable.

The frozen final configuration uses `gpt-5.6-terra` for vision and selection, `high` image detail,
`low` reasoning effort, `meal_recognition_v2`, `canonicalization_v1`, USDA search limit 15 with
normalized multi-query top-five retrieval, and the 100 kcal / 20% P6 limits.

## One development iteration

The first nine-dish run attributed 18 misses and 17 hallucinations to recognition. Descriptions such
as “dark olives” and combined labels such as “bagel with white spread” were poor deterministic
grounding keys, while visual variants could be duplicated. The sole primary iteration created
`meal_recognition_v2`; it requests concise common food identities, merges duplicate visible portions,
separates clearly visible nutritionally meaningful components, and avoids confident identity from
shape or color alone. Retrieval, canonicalization, thresholds, and labels were unchanged.

| Development metric | Before v1 | After v2 | Change |
|---|---:|---:|---:|
| Food precision | 0.292 (n=24 predictions) | 0.593 (n=27) | +0.301 |
| Food recall | 0.280 (n=25 labels) | 0.640 (n=25) | +0.360 |
| Food F1 | 0.286 (n=25 labels) | 0.615 (n=25) | +0.330 |
| Missed / hallucinated foods | 18 / 17 | 9 / 11 | −9 / −6 |
| Preparation accuracy | 1.000 (n=5) | 0.778 (n=9) | −0.222; denominator grew |
| USDA Recall@5 | 0.571 (n=7) | 0.500 (n=14) | −0.071; twice as many verified items reached retrieval |
| Baseline calorie MAE | 217.349 kcal (n=9) | 208.395 kcal (n=9) | −8.954 kcal |
| Baseline meals within ±20% | 0.333 (n=9) | 0.222 (n=9) | −0.111 |
| End-to-end p50 / p95 | 13.913 / 29.260 s (n=9) | 14.142 / 22.347 s (n=9) | +0.229 / −6.913 s |

The recognition hypothesis was supported, but end-to-end nutrition did not improve consistently.
The larger recognized set exposed retrieval misses and portion errors that were previously hidden.

## Development error attribution after v2

Counts below are from `HYBRID_AUTO` and assign each failure to the earliest responsible stage.

| Error | Count | Affected dishes | Estimated consequence | Recommended intervention |
|---|---:|---:|---|---|
| `HALLUCINATED_FOOD` | 11 | 5 | Extra foods can inflate totals or force needless review | Add synonym-aware grading, then improve recognition only for remaining semantic errors |
| `MISSED_FOOD` | 9 | 5 | Omitted calories/macros; high impact for staples and fats | Test multi-component recognition on a larger phone-photo development set |
| `RETRIEVAL_MISS` | 7 | 6 | Correct USDA choice is unavailable to the selector | Improve Foundation/Survey preference, aliases, and query/ranking diagnostics |
| `HIDDEN_INGREDIENT` | 5 | 2 | Oils/sauces can materially understate calories | Make hidden-ingredient suggestions more specific and answerable |
| `WRONG_COOKING_METHOD` | 2 | 2 | Can select a nutritionally different database entry | Preserve preparation only when visually supported |

Recognition remains the largest combined category (20 errors), while retrieval is the largest next
actionable downstream category. No selector error is assigned when the expected USDA candidate was
absent.

## Threshold decision

P6 simulation used seven development items with an exact recognition match, verified USDA truth,
nutrition, and a portion interval. “Materially wrong” means wrong canonical selection or midpoint
portion error above 20%. This conditional sample excludes recognition and retrieval misses.

| Absolute / relative limit | Portion auto-accept | Portion clarification | Unsafe among accepted | Cumulative questions/meal* |
|---|---:|---:|---:|---:|
| 50 kcal / 15% | 0.000 | 1.000 | 0.000 | 2.889 |
| 75 kcal / 20% | 0.000 | 1.000 | 0.000 | 2.889 |
| **100 kcal / 20%** | **0.000** | **1.000** | **0.000** | **2.889** |
| 125 kcal / 25% | 0.000 | 1.000 | 0.000 | 2.889 |
| 150 kcal / 30% | 0.000 | 1.000 | 0.000 | 2.889 |
| 150 kcal / 50% | 0.571 | 0.429 | 0.750 | 2.444 |
| 200 kcal / 60% | 1.000 | 0.000 | 0.857 | 2.111 |

\*Cumulative questions/meal adds simulated portion questions to the 19 canonical/hidden questions
already observed across nine dishes. It is a counterfactual friction estimate, not a second model run.
The 100 kcal / 20% limits were retained: looser settings bought coverage only by accepting too many
materially wrong portions. This is a conservative small-sample decision, not calibration.

## Untouched three-dish holdout

The configuration and dataset hash were frozen before the holdout run. The holdout was run once with
zero infrastructure failures and no post-holdout tuning. Oracle-assisted output equals automatic
output because none of the five generated holdout questions had a valid ground-truth answer among
its offered options; no answer was fabricated.

| Metric | Baseline top-1 | Hybrid auto | Hybrid + oracle HITL |
|---|---:|---:|---:|
| Food precision | 0.375 (n=8 predictions) | 0.375 (n=8) | 0.375 (n=8) |
| Food recall | 0.333 (n=9 labels) | 0.333 (n=9) | 0.333 (n=9) |
| Food F1 | 0.353 (n=9 labels) | 0.353 (n=9) | 0.353 (n=9) |
| Missed / hallucinated foods | 6 / 5 | 6 / 5 | 6 / 5 |
| Preparation accuracy | 0.500 (n=2) | 0.500 (n=2) | 0.500 (n=2) |
| USDA Recall@1 / @3 / @5 | 0.333 / 0.333 / 0.333 (n=3) | same | same |
| Selector accuracy / coverage | 1.000 / 1.000 (n=1) | 1.000 / 1.000 (n=1) | 1.000 / 1.000 (n=1) |
| Selector abstention / wrong / wrong-strong | 0 / 0 / 0 (n=1) | 0 / 0 / 0 (n=1) | 0 / 0 / 0 (n=1) |
| Portion MAE / interval coverage | — (n=0) | — (n=0) | — (n=0) |
| Calorie MAE / median AE | 20.177 / 20.177 kcal (n=2) | — (n=0) | — (n=0) |
| Calorie MAPE | 0.100 (n=2) | — (n=0) | — (n=0) |
| Meals within ±10% / ±20% / ±30% | 0.500 / 1.000 / 1.000 (n=2) | — (n=0) | — (n=0) |
| Protein / carbs / fat MAE | 9.594 / 10.387 / 1.318 g (n=2) | — (n=0) | — (n=0) |
| Unsafe auto-accept | 1.000 (n=2 accepted) | — (n=0 accepted) | — (n=0 accepted) |
| Auto-accept coverage | 0.667 (n=3) | 0.000 (n=3) | 0.000 (n=3) |
| Clarification rate | 0.000 (n=3) | 1.000 (n=3) | 1.000 (n=3) |
| Blocking questions/meal | 0.000 (n=3) | 1.667 (n=3) | 1.667 (n=3) |
| End-to-end p50 / p95 | 13.688 / 17.066 s (n=3) | same shared run | same shared run |

The baseline's low calorie error applies only to the two meals for which it produced totals and does
not make the run safe: both accepted meals were materially wrong because verified foods were missing
or incorrect. The hybrid made the safer choice—no automatic acceptance—but failed usability and
completion: every meal required review and no complete nutrition total was available.

## Licensed SNAPMe phone-photo development recognition

A separate private intake used the USDA SNAPMe archive under CC BY-SA 4.0. One before-photo per
participant was selected deterministically: 30 development cases and 10 participant-disjoint holdout
cases. A provisional visual pass deliberately removed diary-only details such as cooking oil, sugar,
milk fat percentage, brands, and hidden recipe ingredients. An independent human then accepted all 30
development decisions and their uncertainty exclusions. The holdout photos were not visually reviewed
and were not run.

The final runner stopped after vision recognition, preventing ineligible USDA or canonicalization
failures from erasing recognition results. All 30 development cases completed with 77 visible labels.
Strict normalized exact-label-or-approved-alias grading produced:

| Metric | Result |
|---|---:|
| Food precision | 0.225 (16/71 predictions) |
| Food recall | 0.208 (16/77 labels) |
| Food F1 | 0.216 (n=77 labels) |
| Missed / hallucinated foods | 61 / 55 |
| Vision p50 / p95 latency | 5.723 / 9.792 s (n=30) |
| Input / output tokens | 61,292 / 10,286 |
| Vision infrastructure failures | 0/30 |

This result is a strict lexical lower bound, not a semantic recognition score: predictions such as
`pistachio kernels` for `pistachios` are counted wrong unless the alias is independently approved in
advance. A subsequent one-to-one human adjudication reviewed all 55 non-exact predictions: 44 were
semantic matches and 11 were rejected. Combined with 16 automatic exact matches, the adjudicated
result was 60 true positives, 11 false positives, and 17 misses—precision 0.845, recall 0.779, and F1
0.811. No `TOO_BROAD` or unresolved judgments remained.

The development set was not used for a new prompt iteration. SNAPMe amounts and nutrients are
ASA24 dietary-record outputs rather than weighed truth, so portion, hidden-ingredient, nutrition,
USDA retrieval, canonical selection, and preparation metrics remain unmeasured. These are licensed
external phone photos, not owned product captures, and there is no phone-photo holdout claim.

## Next improvements and limitations

1. Improve and diagnose USDA retrieval: Recall@5 was 0.333 on three verified holdout matches and
   retrieval misses were the largest next downstream development failure.
2. Improve multi-component recognition and semantic matching: holdout recall was 0.333 with six
   misses, while several predicted labels were reasonable near-synonyms that strict matching rejects.
3. Make clarification options resolvable: 0/5 holdout questions could be answered from ground truth,
   so oracle assistance could not complete a meal.

The evidence is limited by 12 rig-captured dishes, only three measured holdout meals, one 30-case
licensed phone-photo development run, no phone-photo holdout run, strict lexical recognition matching,
incomplete canonical denominators, external model nondeterminism, USDA-centered ground truth, and no
product-specific owned-capture data. It does not establish clinical accuracy,
production-level generalization, or superiority to another product.
