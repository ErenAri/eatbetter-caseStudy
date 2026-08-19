# Hidden ingredient identity vs risk-surfacing metrics

Hidden ingredients are often not visually identifiable from a meal photo. A system that is evaluated
only on exact hidden-ingredient name recall can be pushed toward hallucinating invisible recipe
ingredients. P5 therefore keeps exact identity scoring but adds separate product-level risk metrics.

## Metric families

### 1. Exact identity

These remain strict normalized-name metrics. No semantic equivalence, recipe prior, or benchmark-specific
alias mapping is introduced.

- `exact_recognition_recall`
- `exact_question_recall`
- `exact_recognition_calorie_weighted_coverage`
- `exact_question_calorie_weighted_coverage`

These answer: **did the system actually identify the measured hidden ingredient by name?**

### 2. Hidden-risk surfacing

Risk surfacing intentionally makes a weaker claim. A hidden-positive meal is considered surfaced when
recognition raises any hidden-ingredient hypothesis or when the evaluated HYBRID state contains any
`HIDDEN_INGREDIENT` clarification.

- `recognition_risk_surface_case_recall`
- `question_risk_surface_case_recall`
- `recognition_risk_surface_calorie_weighted_case_coverage`
- `question_risk_surface_calorie_weighted_case_coverage`
- `silent_hidden_risk_case_rate`

These metrics answer: **did the system avoid silently treating a hidden-positive meal as fully known?**
They do **not** say the hidden ingredient identity was correct.

Calorie-weighted case coverage weights a hidden-positive meal by the sum of measured hidden calories in
that meal. If any hidden risk is surfaced for the meal, its measured hidden kcal contribute to the
risk-surfacing numerator. Exact calorie-weighted coverage remains separate and only credits exact
ingredient names.

### 3. Question burden / false positives

A trivial way to obtain 100% risk-surface recall would be to ask a hidden-ingredient question on every
meal. To make that strategy visible, P5 reports:

- `recognition_risk_surface_false_positive_rate`
- `question_risk_surface_false_positive_rate`
- `mean_hidden_questions_per_positive_meal`
- `mean_hidden_questions_per_complete_negative_meal`

A meal is considered a valid hidden-negative only when `hidden_truth_complete=true` and no hidden
ingredient is marked present. Cases without complete hidden truth are never used as negative labels.

## Clarification-stage semantics

`HYBRID_AUTO` is an **initial-state** view of the clarification pipeline, not necessarily eventual
question reachability. `MealReviewService` intentionally prioritizes unresolved canonical/identity
blockers and returns before hidden-ingredient questions are generated. When a preceding blocker is
answered, the meal is assessed again and a hidden question may then be created.

Therefore:

- `HYBRID_AUTO.question_risk_surface_*` should be read as **initial hidden-question coverage**;
- `HYBRID_ORACLE_HITL.question_risk_surface_*` is the companion measurement for **eventual staged
  reachability after resolvable earlier blockers are progressed**;
- an initial-stage zero must not be described as hidden risk being dropped until the oracle-assisted
  staged state has also been measured.

## Run on an existing frozen development benchmark

P5 makes no model/provider calls. Reuse the same P1 score-first development artifact.

Initial automatic state:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_hidden_risk_analysis `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --cases-jsonl evals\reports\2026-08-19_dev_ranker_score_first_pr_b\cases.jsonl `
  --split development `
  --configuration HYBRID_AUTO `
  --output evals\reports\2026-08-20_hidden_risk_score_first.json
```

Eventual staged reachability:

```powershell
.\backend\.venv\Scripts\python.exe -m evals.run_hidden_risk_analysis `
  --manifest evals\public\nutrition5k\manifest_v2.json `
  --cases-jsonl evals\reports\2026-08-19_dev_ranker_score_first_pr_b\cases.jsonl `
  --split development `
  --configuration HYBRID_ORACLE_HITL `
  --output evals\reports\2026-08-20_hidden_risk_score_first_oracle.json
```

Both reports bind themselves to the exact manifest and `cases.jsonl` bytes using SHA-256 and refuse to
overwrite existing outputs.

## Interpretation policy

Report exact identity and risk surfacing side-by-side. Examples:

- low exact recall + high recognition risk coverage means the model notices uncertainty without
  reliably identifying the hidden ingredient;
- low initial question coverage + high oracle-stage question coverage means risk is staged behind
  earlier blockers rather than lost;
- low initial and oracle-stage question coverage means hidden risk can remain unreachable and the
  routing policy needs investigation;
- high risk coverage + high complete-negative false-positive rate means the system is over-questioning;
- high exact calorie-weighted coverage is stronger evidence than high case-level risk coverage because
  it credits the measured ingredient identity itself.

Do not call case-level risk coverage "hidden ingredient recall". It is a separate safety/UX metric.

## Guardrails

- development-only while the metric definition is being validated;
- no hidden-truth, manifest, alias, or prompt mutation;
- no semantic matching between predicted and true hidden ingredients;
- incomplete hidden truth is never treated as a negative example;
- no provider calls are needed;
- risk surfacing never substitutes for exact identity accuracy;
- initial-stage and eventual-stage question coverage must be reported separately.
