# Vision prompt ablation: v2 vs v3 experimental

This experiment evaluates a **development-only** candidate vision prompt without changing the
production `meal_recognition_v2` prompt.

## Motivation

The corrected frozen-recognition diagnostic showed two opposite granularity failures:

- an intermixed composite can be over-decomposed into embedded ingredients;
- independently portionable foods can be collapsed into one combined label.

A global “split more” or “split less” instruction is therefore not justified. The experimental prompt
uses an **independent portionability** boundary instead:

- preserve intermixed foods as one composite observation when their visible ingredients form one
  serving and are not independently portionable;
- separate visible foods when their amounts can reasonably vary independently in the meal log;
- keep ambiguous fragments/garnishes from becoming duplicate or competing top-level observations;
- use broader identities/alternatives instead of unsupported specific identities.

The candidate prompt contains no benchmark case IDs or FDC IDs.

## Experimental design

The runner performs live vision calls because a prompt change cannot be tested with the frozen P0
recognition fixture. It keeps model, image detail, reasoning effort, dataset, and user context fixed.

For each development case and repeat, both prompts see the same image. Which prompt is called first is
balanced by repeat/case parity. Each repeat is graded independently so model sampling remains visible.

Default design:

- 9 development cases;
- 2 prompts;
- 3 repeats;
- 54 total vision analyses.

No holdout calls are allowed.

## Run

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_vision_prompt_ablation `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --split development `
  --repeats 3 `
  --output evals\reports\2026-08-20_vision_prompt_v2_vs_v3.json
```

The report includes:

- full structured observations for every call;
- image SHA-256 per case;
- prompt SHA-256 values;
- strict precision/recall/F1, misses, and hallucinations per repeat;
- corrected segmentation/identity diagnostic taxonomy per repeat;
- paired candidate-minus-baseline deltas;
- mean metrics across repeats;
- a predeclared directional decision screen.

## Predeclared directional screen

The screen is exploratory evidence, not an automatic promotion rule. The candidate passes only if all
of these are true:

1. mean strict F1 improves;
2. mean strict precision does not decrease;
3. mean hallucinated-food count does not increase;
4. F1 is non-negative versus baseline in at least two thirds of paired repeats;
5. mean strict error units assigned to direct granularity categories decrease.

Direct granularity categories are:

- `UNDER_SEGMENTATION`;
- `OVER_SEGMENTATION`;
- `COMPOSITE_ALIAS_WITH_EXTRA_PREDICTIONS`.

A passing screen is only enough to justify a normal end-to-end development benchmark with the
candidate. It is not evidence for a holdout win and does not prove production superiority.

## Guardrails

- `meal_recognition_v2` remains production/default;
- `meal_recognition_v3_experimental` is an eval artifact only;
- development only;
- no truth, aliases, FDC IDs, or dataset splits are changed;
- strict label/alias recognition metrics remain primary;
- diagnostic categories explain failures but never convert them into matches;
- do not promote the candidate from one favorable repeat while ignoring the others;
- do not run the holdout while iterating on this prompt.
