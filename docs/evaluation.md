# Evaluation protocol and current evidence

The repository contains a strict real-world manifest, real-provider benchmark runner, stage graders,
immutable report writer, rank-1 baseline, automatic hybrid snapshot, and evaluation-only oracle-HITL
mode. No evaluation result is claimed because no labeled private image dataset or live credentials are
available. `evals/reports/p8_unmeasured.json` records that blocker explicitly.

## Dataset unit

One consented meal example contains a private image reference, visible-food labels and aliases,
preparation, independently weighed grams where available, independently calculated nutrition truth,
hidden ingredients and measurement method, manually verified canonical FDC IDs or `UNMAPPABLE`, notes,
and pseudonymous ownership provenance. Split by contributor and meal, not image, to avoid leakage. The
loader rejects duplicate case IDs—including development/holdout overlap—and missing images.

Target 30–40 ordinary phone photos at roughly 75/25 development/holdout. Cover simple, multi-component,
portion-sensitive, sauce/oil, composite, packaged, Turkish/local, low-quality, and non-meal cases.
Counts may overlap. The holdout is a small case-study holdout, never a production benchmark.

## Compared systems

- `BASELINE_TOP1`: P4 observation -> P3 retrieval -> rank 1 -> portion midpoint, with no clarification.
- `HYBRID_AUTO`: P4 -> P3 -> P5 -> P6, captured before any answer.
- `HYBRID_ORACLE_HITL`: evaluation-only upper bound using correct representable answers after questions
  have been generated. It is not automatic accuracy.

Both systems run on the same frozen dataset. Prompt changes create new versioned prompt files and a
new report; they never rewrite historical results.

## Metrics

Food precision/recall/F1, preparation accuracy, hallucinations/misses, recognition-by-category,
retrieval Recall@1/3/5, selector accuracy/coverage/abstention, portion MAE/median/MAPE/interval coverage
and width, meal calorie and macro errors, ±10/20/30% bands, unsafe auto-accept, auto coverage,
clarification types/resolvability/questions per meal, p50/p95 stage latency, completion rate, and actual
token usage are reported independently. Every metric carries its denominator. Null labels are excluded;
MAPE additionally excludes zero truth. Cost is omitted without versioned reliable pricing.

Errors use the taxonomy in `evals/metrics.py`. A reviewer should examine high-confidence errors first,
then cluster failures by taxonomy and slice before changing prompts or policy.

Retrieval misses are excluded from selector accuracy; provider failures are excluded from model errors
and reduce completion rate. A materially wrong auto-accept is an incorrect canonical food or calorie
error greater than 20%. The report retains error cases rather than curating only successes.

## Development iterations and holdout

Run development first, rank its error taxonomy, make one justified prompt/retrieval/policy change, save
it as a new version, and rerun. Two or three iterations are enough. Experiment records belong under
`evals/experiments/`. Simulate documented absolute and relative P6 thresholds, choosing a defensible
safety/friction point rather than the lowest error alone.

Before looking at holdout output, write `evals/reports/final_configuration.json` using the runner's
`--write-final-configuration` option. Holdout requires that snapshot and rejects provider, model,
prompt, retrieval, or threshold drift. Do not tune after inspecting holdout. A genuine bug rerun must be
documented.

Current development iterations: not run. Final configuration: not frozen. Final holdout: not run.

## Retrieval evaluation

`evals/fixtures/retrieval_queries.json` is the non-image P3 retrieval skeleton. Its FDC labels remain
`null` until a reviewer verifies them; no identifier or metric is fabricated. Once labeled, preserve
the provider's candidate order and report Recall@1, Recall@3, and Recall@5 separately from downstream
canonicalization accuracy.

## Recognition evaluation

`evals/datasets/meal_recognition/manifest.json` defines the supported category vocabulary and an empty
case collection ready for consented images and separately reviewed ground truth. Recognition metrics
support explicit aliases, food precision/recall/F1, hallucinated and missed counts, and preparation
accuracy only where labels exist. Hidden-ingredient warnings are not counted as detected foods.

The checked-in recognition report contains null metrics because there are currently zero real cases.
Future runs preserve model, prompt version, reasoning effort, image detail, latency, token usage, and
per-case errors. Portion MAE must exclude cases without measured portions.

## Uncertainty and clarification evaluation

`evals/datasets/uncertainty/manifest.json` is an empty, label-ready P6 scaffold. The checked-in report
therefore contains null metrics rather than fabricated results. With separately reviewed labels, report
portion-interval coverage, calorie-interval coverage, unsafe auto-accept rate, clarification rate,
correction rate, canonical abstention/coverage, and slices by food type and observation certainty.

Use `simulate_thresholds` to compare absolute/relative threshold pairs on the same frozen cases. The
primary safety objective is unsafe auto-accept rate; coverage and clarification rate expose the user
burden tradeoff. Threshold comparisons use the production-inclusive boundary rule.

## Canonicalization evaluation

`evals/datasets/canonicalization/manifest.json` freezes candidate descriptions independently of live
USDA ranking. It currently has three scaffold cases and zero verified FDC labels; all expected IDs and
ranks remain null, so no selector or baseline metric is claimed.

The evaluator separates USDA retrieval Recall@K from selector behavior. Selector metrics are selection
accuracy, selective accuracy, coverage, abstention rate, wrong-selection rate, invalid-rank rate, and
wrong-strong-selection rate. The `USDA_TOP_1` baseline measures how often verified truth is already rank
1. Per-case attribution distinguishes retrieval misses, wrong selection, unnecessary abstention,
invalid ranks, brand mismatches, preparation mismatches, and variant mismatches.

## Limitations and decision status

The intended primary dataset is small, likely single-evaluator, cuisine-limited, USDA-centered, and
single-view; external models remain nondeterministic and the result is not clinically validated. Even
after collection, do not generalize beyond this case-study sample or claim superiority over EatBetter
without running both systems under the same controlled protocol.

Fine-tuning is not justified yet. It would require repeated systematic measured errors, enough labeled
corrections with separate training/evaluation data, and evidence that prompt and retrieval changes have
plateaued. The top three accuracy improvements must be generated from measured error counts; none are
ranked while the dataset is absent.
