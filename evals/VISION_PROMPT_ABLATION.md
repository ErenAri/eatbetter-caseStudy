# Vision prompt ablation: v2 vs v3 experimental

This development-only experiment compares the production `meal_recognition_v2` prompt with an
experimental `meal_recognition_v3_experimental` prompt on the same Nutrition5k development images and
model settings.

The experiment exists because the corrected frozen P4 diagnostic found two opposing granularity
failures: an intermixed composite was over-decomposed, while independently loggable foods were
under-segmented. A global "split more" or "split less" instruction was therefore not justified.

## Candidate policy

The experimental prompt uses **independent portionability**:

- preserve an intermixed composite when its visible ingredients form one serving and are not
  independently portionable without changing the dish;
- separate visually distinguishable foods whose portions could reasonably vary independently;
- keep embedded ingredients, garnishes, and ambiguous fragments from becoming duplicate top-level
  observations;
- prefer a broader identity or explicit alternatives when the visual evidence does not discriminate a
  more specific identity.

This prompt is **eval-only**. The production/default provider continues to load
`meal_recognition_v2.md`.

## Experimental design

The runner calls both prompts live because the prompt itself is the variable; a frozen recognition
fixture would erase the intervention.

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_vision_prompt_ablation `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --repeats 3 `
  --output evals\reports\2026-08-20_vision_prompt_v2_vs_v3.json
```

For each repeat and case:

- both variants use the same model, reasoning effort, image detail, source image, and no user context;
- which prompt runs first alternates by repeat/case parity;
- each repeat is graded independently;
- full structured observations are retained;
- image bytes and prompt text are SHA-256 bound in the report.

The runner is development-only and rejects holdout.

## Predeclared directional screen

Before measured v3 results were available, the candidate was declared to pass only when **all** of the
following held across the paired repeats:

1. mean strict F1 improves;
2. mean strict precision does not decrease;
3. mean hallucinated-food count does not increase;
4. candidate F1 is non-negative versus baseline in at least two thirds of repeats;
5. mean strict error units in the direct granularity categories decrease.

The direct granularity categories are:

- `UNDER_SEGMENTATION`
- `OVER_SEGMENTATION`
- `COMPOSITE_ALIAS_WITH_EXTRA_PREDICTIONS`

This is a directional development screen, not a statistical significance claim. Passing would only
justify a normal end-to-end development benchmark; it would not automatically promote the prompt.

## Measured result — candidate rejected

The three-repeat paired live experiment **failed the predeclared screen**.

Mean strict metrics:

| Metric | v2 baseline | v3 experimental | Delta (v3 - v2) |
| --- | ---: | ---: | ---: |
| F1 | 57.52% | 49.32% | **-8.20 pp** |
| Precision | 54.20% | 52.31% | **-1.89 pp** |
| Recall | 61.33% | 46.67% | **-14.67 pp** |
| Hallucinated foods | 13.00 | 10.67 | **-2.33** |
| Missed foods | 9.67 | 13.33 | **+3.67** |
| Direct-granularity strict units | 3.33 | 3.00 | **-0.33** |

Paired F1 deltas were negative in **all three repeats**: approximately -7.00 pp, -10.47 pp, and
-7.12 pp. The candidate therefore had zero non-negative F1 repeats out of the required two.

The candidate did accomplish one intended safety direction: it emitted fewer hallucinated top-level
foods and slightly reduced direct-granularity error units. That gain came at an unacceptable recall
cost. The identity/duplicate restraint was too conservative and frequently replaced or omitted
visually relevant ground-truth foods.

Observed failure patterns included:

- `pasta salad` repeatedly collapsing to the broader `mixed green salad` identity;
- `brown rice` becoming `rice mixed dish` / `rice with mixed vegetables`, while `arugula` was omitted;
- `couscous` becoming `couscous salad` / `vegetable couscous`;
- the target `bagel` + `cream cheese` under-segmentation remaining as `bagel with cream cheese`.

These failures show that the experimental prompt traded false positives for false negatives rather
than improving recognition accuracy. The lower hallucination count must not be presented as an
accuracy win in isolation.

### Decision

- **Do not promote `meal_recognition_v3_experimental`.**
- Keep production `meal_recognition_v2` unchanged.
- Do not spend another prompt iteration tuning these nine development images; that would increase
  benchmark-overfitting risk.
- Preserve this failed experiment as evidence of measured iteration and a rejected tradeoff.
- Move the next accuracy work to hidden-ingredient/risk coverage, where exact invisible-ingredient
  name recall is known to be a poor sole product metric.

## Guardrails

- no production prompt switch;
- no holdout calls;
- no manifest, acceptable-alias, or FDC mutation;
- no claim that lower hallucinations alone means better recognition;
- the failed candidate remains an experiment, not a shipping configuration;
- the exact report is retained as the evidence artifact.
