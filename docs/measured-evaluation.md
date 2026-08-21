# Measured evaluation — public secondary and phone-photo evidence

Status date: 2026-08-20.

## Evidence boundary

This case study uses two complementary external datasets:

1. **Nutrition5k secondary subset** — 12 rig-captured dishes with published measured portions/nutrition and reviewed USDA mappings. It supports stage-level end-to-end diagnostics but does not reproduce ordinary single-phone capture.
2. **SNAPMe phone-photo subset** — 30 development and 10 participant-disjoint holdout phone photos with reviewed visible-food labels. It supports recognition-only evidence; its dietary-record amounts are not weighed ground truth.

The private product-specific owned/consented dataset remains empty. No result below establishes clinical accuracy, production-level generalization, or numerical superiority to EatBetter.

### Nutrition5k versioning boundary

`nutrition5k-public-secondary-v1` was the original frozen 9-development / 3-holdout secondary evaluation. After those results were observed, the evaluation truth contract was corrected and versioned as `nutrition5k-public-secondary-v2` while preserving the same case IDs.

Therefore the three v2 secondary holdout IDs are **historical holdout cases inherited from v1, not a newly untouched v2 holdout**. They remain useful for historical comparison only. A future final holdout requires previously unseen cases.

The v2 dataset uses canonical JSON + image SHA-256 split locking and adds complete hidden-truth semantics and measured hidden calories where supported by Nutrition5k metadata.

| Nutrition5k v2 fact | Count |
|---|---:|
| Total / development / historical holdout IDs | 12 / 9 / 3 |
| Dishes with measured portions | 12 |
| Visible labeled items | 34 |
| Visible items with independently reviewed USDA mappings | 30 |
| Visible items marked `UNMAPPABLE` | 4 |
| Recorded hidden ingredients | 13 |

## Production evaluation pipeline

Real runs reject demo/unconfigured providers. The measured pipeline uses:

```text
image
  ↓
OpenAI structured vision observation
  ↓
USDA retrieval/ranking
  ↓
OpenAI rank-only SELECT/ABSTAIN canonicalization
  ↓
USDA detail grounding
  ↓
deterministic uncertainty / clarification
```

The frozen product configuration uses `gpt-5.6-terra`, high image detail, low reasoning effort, `meal_recognition_v2`, `canonicalization_v1`, USDA normalized multi-query retrieval, and the 100 kcal / 20% uncertainty limits.

Ground truth is loaded only by the grader. It is never sent into recognition, retrieval, selection, or clarification generation.

**Shipped configuration no longer matches the benchmarked one.** The runtime recognition prompt is now
`meal_recognition_v4`, while every number in this document was produced under `meal_recognition_v2`.
Because `PROMPT_VERSION` is global, this applies to `NUTRITION_PROVIDER=usda` as well as `ai`. The
results below remain valid as a record of what that frozen configuration produced; they should not be
read as describing current runtime behaviour. `meal_recognition_v2.md` itself is unchanged and
hash-guarded against the SNAPMe configuration lock.

## Primary Nutrition5k development iteration

The first nine-dish run exposed recognition as the largest early failure source. The single primary prompt iteration created `meal_recognition_v2`: concise common identities, duplicate merging, separation of clearly visible nutritionally meaningful components, and less confident identity from shape/color alone.

Retrieval, canonicalization, thresholds, and labels were held fixed.

| Development metric | v1 prompt | v2 prompt | Change |
|---|---:|---:|---:|
| Food precision | 0.292 | 0.593 | +0.301 |
| Food recall | 0.280 | 0.640 | +0.360 |
| Food F1 | 0.286 | 0.615 | +0.330 |
| Missed / hallucinated foods | 18 / 17 | 9 / 11 | −9 / −6 |
| Preparation accuracy | 1.000 (n=5) | 0.778 (n=9) | denominator grew |
| USDA Recall@5 | 0.571 (n=7) | 0.500 (n=14) | more verified items reached retrieval |
| Baseline calorie MAE | 217.349 kcal | 208.395 kcal | −8.954 kcal |
| Baseline meals within ±20% | 0.333 | 0.222 | −0.111 |
| End-to-end p50 / p95 | 13.913 / 29.260 s | 14.142 / 22.347 s | p95 improved |

Recognition improved substantially, but end-to-end nutrition did not improve consistently. Better recognition exposed downstream retrieval and portion errors that the earlier prompt had hidden.

## Error attribution after recognition v2

`HYBRID_AUTO` assigns each failure to the earliest responsible stage.

| Error | Count | Affected dishes | Interpretation |
|---|---:|---:|---|
| `HALLUCINATED_FOOD` | 11 | 5 | extra foods can inflate totals or force review |
| `MISSED_FOOD` | 9 | 5 | omitted foods can understate calories/macros |
| `RETRIEVAL_MISS` | 7 | 6 | correct USDA identity unavailable to selector |
| `HIDDEN_INGREDIENT` | 5 | 2 | invisible oils/sauces can materially alter totals |
| `WRONG_COOKING_METHOD` | 2 | 2 | preparation can change canonical choice/nutrition |

Recognition remained the largest combined category; retrieval was the largest downstream actionable category.

## Threshold decision

The 100 kcal / 20% P6 limits were retained after a seven-item conditional simulation containing exact recognition matches, verified USDA truth, nutrition, and portion intervals.

| Absolute / relative limit | Portion auto-accept | Portion clarification | Unsafe among accepted |
|---|---:|---:|---:|
| 50 kcal / 15% | 0.000 | 1.000 | 0.000 |
| 75 kcal / 20% | 0.000 | 1.000 | 0.000 |
| **100 kcal / 20%** | **0.000** | **1.000** | **0.000** |
| 125 kcal / 25% | 0.000 | 1.000 | 0.000 |
| 150 kcal / 30% | 0.000 | 1.000 | 0.000 |
| 150 kcal / 50% | 0.571 | 0.429 | 0.750 |
| 200 kcal / 60% | 1.000 | 0.000 | 0.857 |

This is a conservative small-sample engineering choice, not calibration.

### Absolute floor added to the relative arm

The two limits above were independent, so **any** item whose calorie range varied by more than 20%
raised a blocking question regardless of how few calories were involved. On a real six-item photo,
four of six questions concerned garnishes totalling 38 kcal of uncertainty on a ~790 kcal meal —
including fresh herbs at 7 kcal. That contradicted this repository's own stated rationale, which uses
parsley as the example of something that should *not* interrupt.

The relative arm is now gated behind a minimum absolute swing (`MIN_RELATIVE_TRIGGER_KCAL`, default
25 kcal). On the same photo this reduced portion questions from six to three, leaving the two items
carrying 93% of the meal's calories plus one the model flagged as low-familiarity. The floor is an
engineering hypothesis on the same footing as the 100 kcal / 20% limits — it has not been swept
against the threshold table above.

## Historical Nutrition5k three-dish secondary holdout

The table below preserves the original one-time secondary holdout evidence from the v1 experiment series. The same three IDs are present in v2 for historical comparison, but because they had already been observed they are not presented as a newly untouched v2 holdout.

| Metric | Baseline top-1 | Hybrid auto | Hybrid + oracle HITL |
|---|---:|---:|---:|
| Food precision | 0.375 (n=8 predictions) | 0.375 | 0.375 |
| Food recall | 0.333 (n=9 labels) | 0.333 | 0.333 |
| Food F1 | 0.353 | 0.353 | 0.353 |
| Missed / hallucinated foods | 6 / 5 | 6 / 5 | 6 / 5 |
| Preparation accuracy | 0.500 (n=2) | 0.500 | 0.500 |
| USDA Recall@1 / @3 / @5 | 0.333 / 0.333 / 0.333 (n=3) | same | same |
| Selector accuracy / coverage | 1.000 / 1.000 (n=1) | 1.000 / 1.000 | 1.000 / 1.000 |
| Calorie MAE / median AE | 20.177 / 20.177 kcal (n=2) | — | — |
| Meals within ±20% | 1.000 (n=2 totals) | — | — |
| Unsafe auto-accept | 1.000 (2/2 accepted) | — | — |
| Auto-accept coverage | 0.667 (n=3) | 0.000 | 0.000 |
| Clarification rate | 0.000 | 1.000 | 1.000 |
| Blocking questions/meal | 0.000 | 1.667 | 1.667 |
| End-to-end p50 / p95 | 13.688 / 17.066 s | shared run | shared run |

The low baseline calorie MAE applies only to the two meals for which totals were produced and is not a safety win: both accepted meals were materially wrong because required verified foods were missing or incorrect. The hybrid avoided silent acceptance but failed completion/usability on this tiny secondary sample.

## Controlled downstream ablations on frozen recognition

To isolate retrieval/selector behavior from vision nondeterminism, the nine development observations were captured once into an immutable frozen recognition fixture. Downstream experiments replay the same fixture and validate case IDs, image hashes, schema, dataset version, and fixture SHA before execution.

### Ranker ablation

| Metric | Semantic production ranker | Score-first ablation |
|---|---:|---:|
| Food F1 | 55.6% | 55.6% |
| USDA Recall@1 | 3/13 = 23.08% | 4/13 = 30.77% |
| USDA Recall@3 | 8/13 = 61.54% | 8/13 = 61.54% |
| USDA Recall@5 | 8/13 = 61.54% | 8/13 = 61.54% |
| Selector accuracy | 3/8 = 37.5% | 6/8 = 75.0% |
| Wrong strong selection | 5/8 = 62.5% | 2/8 = 25.0% |
| Calorie MAE | 100.84 kcal | 164.20 kcal |
| Meals within ±20% | 25.0% | 37.5% |

Interpretation: score-first improved exact Recall@1 and selector exact-ID accuracy on this frozen development input, but **did not improve Recall@3 or Recall@5** and produced worse calorie MAE. It remains an ablation control, not an automatic product promotion.

### Selector permutation robustness

Eight eligible items received repeated controls and candidate-order/rerank perturbations.

- Control selector accuracy: 6/8 = 75%.
- Control repeat instability: 0/8.
- Array-position sensitivity: 2/8 = 25%.
- Rank-label/rerank sensitivity: 3/8 = 37.5%.
- Condition exact-ID accuracies: controls 75%, array reversed 75%, array rotate-left 50%, rerank reversed 50%, rerank rotate-left 62.5%.

Exact-ID sensitivity can overstate meaningful harm because near-equivalent USDA records may differ by ID. These numbers are robustness diagnostics, not a claim that 37.5% of selections are semantically harmful.

## Recognition error diagnostics and rejected v3 prompt

A frozen lexical segmentation diagnostic conserved the primary strict error units rather than silently approving new aliases. It found 24 strict errors across 15 structural events, including both under-segmentation and extra-modifier/partial-overlap patterns. The errors pointed in opposing directions; a generic “split more” or “split less” prompt change was not justified.

A paired live v2-vs-v3 prompt ablation was therefore predeclared and run three times on the same nine development images.

| Mean strict metric | v2 production | v3 experimental | Delta |
|---|---:|---:|---:|
| F1 | 57.52% | 49.32% | **−8.20 pp** |
| Precision | 54.20% | 52.31% | −1.89 pp |
| Recall | 61.33% | 46.67% | **−14.67 pp** |
| Hallucinated foods | 13.00 | 10.67 | −2.33 |
| Missed foods | 9.67 | 13.33 | +3.67 |

All three paired repeats had worse F1. The v3 candidate reduced some false positives but paid an unacceptable recall cost, so it was **rejected** and production stayed on `meal_recognition_v2`. No further prompt tuning was performed on the same nine cases.

## Hidden ingredients: identity vs risk surfacing

Invisible ingredients are not reliably identifiable by name from pixels, so exact identity and risk surfacing are reported separately.

On the frozen development artifact:

- Exact hidden recognition recall: **0/5**.
- Recognition risk-surface case coverage: **2/2 hidden-positive meals = 100%**.
- Recognition calorie-weighted risk-surface coverage: **100%**.
- Recognition risk-surface false-positive rate on complete negatives: **5/7 = 71.43%**.
- Initial `HYBRID_AUTO` hidden-question risk-surface coverage: **0/2**.
- Initial hidden-question false-positive rate: **2/7 = 28.57%**.

The high risk-surface number is **not hidden ingredient recall**; it only means the system did not silently treat the measured hidden-positive meals as fully known.

An oracle-progressed staged run still produced 0/2 hidden-question coverage. A dedicated reachability trace then showed both positive meals were deferred behind earlier `CANONICAL_SELECTION` blockers and found **0 unexplained hidden-routing gaps**. The hidden-stage ordering was therefore not changed.

## Clarification recovery root-cause trace

The next artifact-only trace classified 11 unresolved canonical/identity blockers:

| Root cause | Count |
|---|---:|
| `NO_TRUTH_ASSOCIATION_REMOVE_MISSING` | 5 |
| `RETRIEVAL_OPTION_MISS` | 3 |
| `OBSERVED_NAME_ASSOCIATION_GAP_CORRECT_FDC_OFFERED` | 2 |
| `UNMAPPABLE_TRUTH_REQUIRES_MANUAL_RECOVERY` | 1 |

The two association cases included composite/component ambiguity, so the oracle evaluator was **not** relaxed simply because an acceptable component FDC ID appeared in the options.

The product-supported fix was narrower: candidate-bearing `CANONICAL_SELECTION` clarifications now include a direct **“This food is not in my meal” / `REMOVE_ITEM`** recovery. This lets a user remove a hallucinated food without forcing additional grounding or model work. Regression tests cover the path.

## SNAPMe phone-photo recognition

A private intake used the licensed USDA SNAPMe archive. One before-photo per participant was selected deterministically: 30 development and 10 participant-disjoint holdout cases. Diary-only details such as hidden oil, sugar, milk-fat percentage, brands, and invisible recipe ingredients were excluded from visible-food truth before scoring.

### Development

- 30/30 cases completed.
- 77 reviewed visible labels; 71 predictions.
- Strict lexical precision 0.225, recall 0.208, F1 0.216.
- One-to-one semantic adjudication: 60 TP, 11 FP, 17 misses.
- Semantic precision **0.845**, recall **0.779**, F1 **0.811**.

No new prompt iteration was performed on this development result.

### Participant-disjoint holdout

- 10/10 cases completed with no vision infrastructure failures.
- 36 reviewed visible labels; 34 predictions.
- Strict lexical precision 0.382, recall 0.361, F1 0.371.
- One-to-one semantic adjudication: 29 TP, 5 FP, 7 misses.
- Semantic precision **0.853**, recall **0.806**, F1 **0.829**.

SNAPMe amounts/nutrients are ASA24 dietary-record outputs rather than weighed truth. This result therefore supports **visible-food recognition only** and does not measure portion, hidden ingredients, nutrition, USDA grounding, canonical selection, preparation, or owned-product captures.

## Out-of-distribution qualitative probe (n=5, 2026-08-20)

This is **not a measurement**. Five photos, one run each, live providers, stock food photography
rather than phone capture, no ground-truth portions, no scoring. It generates hypotheses; it settles
nothing, and none of it belongs in a summary table beside the results above.

Two of the five dishes are Turkish and absent from both benchmark datasets, which is why the probe
was run: neither Nutrition5k nor SNAPMe tests cuisine outside a USDA-centred Western distribution.

| Photo | Recognition | Candidates offered | Result |
|---|---|---|---|
| Lahmacun | topped flatbread, mixed fresh herbs, tomato, red onion, lemon wedge | herbs → `Fish, bass, fresh water, mixed species, raw` at rank 1 | 0 kcal, blocked |
| Adana kebab | ground meat kebabs + 5 others | `Meat, ground, NFS`, then deer, bison, elk | 0 kcal, blocked |
| Pan pizza | pizza, baked | 5 × DIGIORNO frozen | 0 kcal, blocked |
| Bacon cheeseburger | bacon cheeseburger, seasoned French fries, ketchup | run A: `Cheeseburger, NFS`; run B: 5 bacon products, no burger | 0 kcal, blocked |
| Wok plate | stir-fried noodles, breaded fried chicken, beef with broccoli | noodles → mushroom and lentil entries | 0 kcal, blocked |

Recognition held up on unseen cuisine — tomato, red onion, lemon, ketchup, French fries and breaded
fried chicken all grounded correctly. The failures concentrated downstream:

1. **Retrieval matched on modifiers rather than head nouns.** The full observed phrase is sent as the
   query, so qualifiers dominate the lexical match.
2. **The selector abstained on a correct rank-1 candidate** (`Beef and broccoli`, FNDDS). Holdout
   selector accuracy of 1.000 rests on n=1 and should not be read as characteristic.
3. **No hidden-ingredient question fired on any of the five**, despite deep-fried potatoes, battered
   chicken, pizza dough oil, and ~20% fat lamb.
4. **0/5 meals produced nutrition**, reproducing the 0% auto-accept coverage recorded on the
   historical holdout, on data the system had never seen.
5. **Run-to-run variance is material.** The same burger photo produced a usable candidate list in one
   run and five bacon products in another.

Ordering compounded the problem: "Search for another food" sat below five plausible wrong options, so
the interface steered toward the error.

## Final interpretation

The evidence supports the following case-study conclusions:

1. The hybrid architecture makes model uncertainty measurable and recoverable instead of letting the LLM directly author nutrition.
2. Phone-photo visible-food recognition is promising on the small participant-disjoint SNAPMe holdout, but that is not end-to-end nutrition validation.
3. Nutrition5k secondary experiments show that retrieval and clarification completion remain major downstream bottlenecks.
4. Controlled ablations matter: the v3 prompt was rejected despite reducing hallucinations because total F1/recall regressed.
5. Hidden-ingredient safety requires separate exact-identity, risk-surface, and question-burden metrics.
6. The latest product fix came from a root-cause trace (`REMOVE_ITEM` recovery), not benchmark-specific aliases or post-hoc truth edits.

## Remaining limitations / next improvements

1. Collect owned or explicitly consented ordinary phone meals with kitchen-scale portions and measured oil/sauce.
2. Create a genuinely unseen final holdout; do not reuse the already-inspected Nutrition5k historical holdout IDs as untouched evidence.
3. Improve USDA retrieval on new development evidence without adding benchmark-specific acceptable FDC IDs post hoc. The n=5 probe suggests a specific mechanism to test first: the full observed phrase is sent as the query, so modifiers outweigh head nouns. Retrieving on the head noun and re-ranking against the full phrase is the cheapest hypothesis available.
4. Make portion questions answerable in the units a person can actually produce. `USER_HOUSEHOLD_UNIT` exists and the USDA `foodPortions` gram weights are retrieved and then discarded before reaching the item; asking "one whole / half" instead of "about 180 g" is the likeliest route to resolvable portions, and 0/5 historical holdout questions were oracle-resolvable.
5. Gate the candidate list on relevance. When no candidate clears a floor, lead with manual search rather than ranking five wrong options above it.
6. Measure clarification completion, user burden, and unsafe auto-accept on a larger representative product set.
7. Add production JWT/persistence/storage/monitoring before deployment.
8. Measure the `ai` nutrition path. It currently has unit tests and zero accuracy evidence; the Nutrition5k development split with measured portions is the correct first target.

The repository deliberately keeps these limitations visible instead of turning incomplete denominators into a single headline “accuracy” percentage.
