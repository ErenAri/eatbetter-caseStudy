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

## Clarification lifecycle

Generation priority is food identity, then material/unknown hidden ingredients, then portion. Stable
keys make generation idempotent and hidden ingredient names are normalized and deduplicated at meal
scope. Candidate questions contain only stored candidate ranks. With zero candidates, the only actions
are manual search or removal. Portion choices contain server-generated grams; custom grams are accepted
only by portion questions.

Answers are validated against the persisted choices. Replaying the same answer is a no-op; replaying a
different answer returns `409 CLARIFICATION_ALREADY_ANSWERED`. A canonical answer grounds the selected
stored candidate through P3 and reassesses without rerunning P5. `Not sure` is recorded but does not
satisfy a blocking hidden-ingredient question. Generic hidden concepts such as “oil” are never silently
mapped to one canonical food.

## Confirmation invariant

Every active item must have a canonical identity, stored nutrition snapshot, resolved portion, and final
deterministic nutrition. No unresolved blocking clarification may remain. Removed items do not block.
Confirmation performs no model call.
