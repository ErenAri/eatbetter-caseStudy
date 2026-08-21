# Deterministic uncertainty and clarification

P6 is a policy layer over P4 observations, P5 candidate selection, and P3 nutrition snapshots. It does
not ask an AI model to invent probabilities, make the final safety decision, calculate nutrition, or
write clarification questions.

## Risk policy

The policy emits `LOW`, `MEDIUM`, or `HIGH` plus stable reason codes. `HIGH` is blocking. A `MEDIUM`
observation alone does not interrupt the user. The full set of blocking reasons is:

| Reason code | Raised when |
|---|---|
| `CANONICAL_UNRESOLVED` | no canonical identity and no candidates were retrieved |
| `CANONICAL_AMBIGUOUS` | no canonical identity but candidates exist to choose between |
| `MISSING_NUTRITION_SNAPSHOT` | identity resolved but no stored per-100 g nutrition |
| `PORTION_UNKNOWN` | the observation supplied no portion interval |
| `INVALID_PORTION_RANGE` | the interval is negative or inverted |
| `ABSOLUTE_CALORIE_UNCERTAINTY` | the calorie swing exceeds the absolute limit |
| `RELATIVE_CALORIE_UNCERTAINTY` | the swing exceeds the relative limit *and* clears the absolute floor |
| `LOW_OBSERVATION_CERTAINTY` | the vision observation reported low certainty about what it saw |
| `LOW_NUTRITION_FAMILIARITY` | the nutrition provider reported low familiarity with this food |
| `LOW_NUTRITION_CONSENSUS` | repeated nutrition samples disagreed beyond the spread limit |
| `MATERIAL_HIDDEN_INGREDIENT` | an affirmed hidden ingredient can materially change the total |
| `UNKNOWN_HIDDEN_INGREDIENT` | hidden-ingredient presence is unresolved |

`LOW_NUTRITION_FAMILIARITY` and `LOW_NUTRITION_CONSENSUS` exist because the AI nutrition path has no
external provenance to check a value against. They are distinct signals and neither subsumes the
other: familiarity is the provider's self-reported knowledge of the food, while consensus measures
disagreement across repeated samples of the same food. A food can be reported as well known and still
produce inconsistent estimates, and a food the provider does not know can produce a perfectly stable
default. Both are recorded as `nutrition_familiarity` and `nutrition_consensus_spread` on the item;
providers that do not supply them (USDA, demo) leave both null and neither reason can fire.

Neither is a calibrated probability. `LOW_OBSERVATION_CERTAINTY` is deliberately kept separate from
both — it describes confidence about *what was seen*, not about the food's composition.

For a grounded item, nutrition at the estimated minimum and maximum grams is calculated with `Decimal`
from the stored per-100 g snapshot. Absolute calorie uncertainty is `max - min`. Relative uncertainty
is `(max - min) / ((max + min) / 2)`. A zero midpoint with a zero interval has zero relative
uncertainty; a zero midpoint with nonzero spread is unsafe.

The configured thresholds are inclusive: exactly 100 kcal and exactly 20% are auto-acceptable. Values
greater than the absolute threshold always require portion clarification. The relative threshold is
additionally gated by a minimum absolute floor (25 kcal by default): a swing greater than 20% only
requires clarification once the absolute swing also exceeds that floor, so a large percentage change
on a handful of kcal (a garnish) does not interrupt the user the way it would on a calorie-dense item.
Safe estimates use the range midpoint and record `AUTO_ESTIMATE`; direct user grams record `USER`; a
provider-backed household option records `USER_HOUSEHOLD_UNIT`. There is deliberately no universal
household-unit conversion.

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

Zero candidates now arises on two distinct paths. USDA retrieval can return nothing usable, and the AI
nutrition provider deliberately returns no candidate for a food it does not recognize rather than
inventing a plausible value. Both land on the same `CANONICAL_UNRESOLVED` question, so a refusal is
surfaced as a normal identity clarification instead of a failure.

Removing an item through either identity question records a `removed_item` correction, so an item the
user discarded remains visible in the correction history rather than disappearing from the audit
trail.

Candidate labels expose provenance as secondary metadata such as `FoodData Central · FNDDS` or
`FoodData Central · Foundation`; provenance is not presented as evidence that the photo match is
correct. AI-estimated candidates are labelled `AI ESTIMATE — NOT A DATABASE RECORD` through a separate
`provenance_note` field. That separation is deliberate: `data_type` is a real database field that is
forwarded to the constrained selector as evidence, whereas `provenance_note` is user-facing only and
is never sent to a model. Putting a warning string in `data_type` previously caused the selector to
read "not a database record" as a reason to abstain, so the two channels are now kept apart. Portion choices show the actual estimated gram values instead of qualitative
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
