# Deterministic uncertainty and clarification

P6 is a policy layer over P4 observations, P5 candidate selection, and P3 nutrition snapshots. It does
not ask an AI model to invent probabilities, make the final safety decision, calculate nutrition, or
write clarification questions.

## Risk policy

The policy emits `LOW`, `MEDIUM`, or `HIGH` plus stable reason codes. `HIGH` is blocking. A `MEDIUM`
observation alone does not interrupt the user. `LOW` observation certainty, unresolved or ambiguous
identity, missing nutrition, unknown portions, unsafe calorie ranges, and material/unknown hidden
ingredients block automatic acceptance.

For a grounded item, nutrition at the estimated minimum and maximum grams is calculated with `Decimal`
from the stored per-100 g snapshot. Absolute calorie uncertainty is `max - min`. Relative uncertainty
is `(max - min) / ((max + min) / 2)`. A zero midpoint with a zero interval has zero relative
uncertainty; a zero midpoint with nonzero spread is unsafe.

The configured thresholds are inclusive: exactly 100 kcal and exactly 20% are auto-acceptable. Only
values greater than either threshold require portion clarification. Safe estimates use the range
midpoint and record `AUTO_ESTIMATE`; direct user grams record `USER`; a provider-backed household
option records `USER_HOUSEHOLD_UNIT`. There is deliberately no universal household-unit conversion.

## Canonical-selection safety gate

The constrained selector may still return `SELECT` only for a supplied candidate rank, but model
`EXACT`/`STRONG` labels are not treated as sufficient evidence by themselves. Before grounding a
model-selected candidate, the application applies a deterministic identity/preparation compatibility
gate over the normalized grounding query and the persisted candidate names. Unsupported selections
are converted to `ABSTAIN` and routed to human review instead of being silently grounded.

This gate is intentionally conservative and is not a calibrated confidence score. Its purpose is to
prevent a model from making a self-certified strong selection that is materially inconsistent with
the observable food identity or preparation state.

## Clarification lifecycle

Generation priority is food identity, then material/unknown hidden ingredients, then portion. Stable
keys make generation idempotent and hidden ingredient names are normalized and deduplicated at meal
scope. Candidate questions contain only stored candidate ranks plus an explicit persisted
`MANUAL_SEARCH` recovery action. With zero candidates, the available actions are manual search or
removal. A user is therefore not trapped when the correct FoodData Central record is absent from the
initial candidate set.

Candidate labels expose database provenance as secondary metadata such as `FoodData Central · FNDDS`
or `FoodData Central · Foundation`; provenance is not presented as evidence that the photo match is
correct. Portion choices show the actual estimated gram values instead of qualitative
`Smaller`/`Larger` anchors, while custom grams remain available. Hidden-ingredient wording explicitly
asks about use the photo may not show and does not claim that a plausible ingredient was present.

Answers are validated against the persisted choices. Replaying the same answer is a no-op; replaying a
different answer returns `409 CLARIFICATION_ALREADY_ANSWERED`. A canonical answer grounds the selected
stored candidate through P3 and reassesses without rerunning P5. `MANUAL_SEARCH` deliberately leaves
the blocker unresolved until the replacement flow succeeds. `Not sure` is recorded but does not
satisfy a blocking hidden-ingredient question. Generic hidden concepts such as “oil” are never silently
mapped to one canonical food.

## Evaluation

`clarification_resolvability` remains a strict measured metric: a question counts as resolvable only
when its offered answer set contains a ground-truth-valid answer. The manual-search recovery path does
not retroactively convert an unresolvable generated option set into a successful measured result. This
keeps the existing `0/5` holdout finding honest and makes future improvements comparable rather than
inflating the metric through UI escape hatches.

## Confirmation invariant

Every active item must have a canonical identity, stored nutrition snapshot, resolved portion, and final
deterministic nutrition. No unresolved blocking clarification may remain. Removed items do not block.
Confirmation performs no model call.
