# Exploratory Android QA — 2026-08-18

## Release recommendation

**P1/P2 REMEDIATION VERIFIED — GO for the scoped case-study demonstration, subject to the device and accuracy boundaries below.**

The core photo upload, real OpenAI recognition, USDA requests, review, confirmation, Today totals,
and meal-detail navigation work. The pass nevertheless found user-visible dead ends and misleading
lifecycle/provenance states that the automated suite does not cover.

Severity definitions used here:

- **P0:** safety, security, privacy, irreversible data loss, or materially dangerous nutrition output.
- **P1:** release blocker for a core workflow or the planned case-study demonstration.
- **P2:** important defect with a workaround or a narrower scope.
- **P3:** polish, consistency, or low-impact usability issue.

No P0 issue was observed. Five P1 issues were reproduced in the original pass and fixed in the
follow-up described below.

## P1 remediation verification — 2026-08-18

All five original P1 findings are resolved in the current revision:

- `EB-QA-001`: USDA searches now use generic reference datasets, deterministic query aliases for
  common observation/database vocabulary gaps, deduplication, and user-facing data-type/brand/serving
  labels. A fresh real-provider run on the same pasta image returned distinguishable candidates.
  When USDA has no defensible generic exact match (notably meatballs), the app still abstains and
  exposes the manual replacement path rather than inventing a match.
- `EB-QA-002`: removing an item now dismisses and satisfies its pending clarifications. The mobile
  client independently filters to pending blockers associated with active items.
- `EB-QA-003`: non-confirmed shells render as `Incomplete`, never as saved zero-calorie meals. Detail
  copy is lifecycle-aware; attached recoverable attempts can resume analysis, and incomplete attempts
  expose an explicit discard/start-over action.
- `EB-QA-004`: `None of these` opens a replacement editor for the original item. The server replaces
  that item atomically, preserves the correction audit, supersedes the old clarification, and creates
  a new clarification if the replacement still cannot be grounded.
- `EB-QA-005`: deterministic fixture candidates carry embedded snapshots and are grounded without the
  configured live nutrition provider. The Android emulator advanced from `Cream sauce` to portion
  review while the backend remained configured for live USDA.

Verification evidence: backend `122 passed`, evaluation `40 passed`, mobile `19 passed`, TypeScript
clean, Expo Doctor `21/21`, real-provider pasta rerun completed in `NEEDS_REVIEW`, and targeted Android
emulator checks passed for incomplete-state copy, manual-replacement routing, and fixture selection.

## P2 remediation verification — 2026-08-18

The current revision resolves `EB-QA-006` through `EB-QA-013` and the related P3 loading defect:

- `EB-QA-006`: `/health` reports `demo`, `live`, or `unconfigured` from runtime adapter selection and
  credential readiness. Today renders that status; Meal Detail derives nutrition and photo provenance
  from stored meal evidence.
- `EB-QA-007`: the explicit zero-gram `None` answer removes the item from active foods and totals while
  retaining portion and removal corrections in the audit.
- `EB-QA-008`: every documented stable vision, canonicalization, and USDA failure has actionable
  mobile copy; provider internals remain hidden.
- `EB-QA-009`: capture attempts persist request context, photo URI, and attached meal ID in the app's
  document storage. They restore after an activity/process restart and remain resumable after cancel.
- `EB-QA-010`: edit, add, and replacement forms reset only after a successful mutation and retain
  their entered values after failure.
- `EB-QA-011`: ordinary update/add/replacement paths require finite positive grams in both client and
  API/service validation. Zero is reserved for the explicit clarification meaning `None`.
- `EB-QA-012`: hidden-ingredient prompts whose normalized food tokens overlap an active visible food
  are suppressed; materially distinct additions such as cooking oil remain eligible.
- `EB-QA-013`: upload and analysis are separate phases, followed by monotonic coarse status messages;
  no fabricated percentage or backwards-cycling stage is shown.
- `EB-QA-014`: Today no longer renders a stale capture action from a previous list while loading or
  displaying an error.

Verification: backend `127 passed`, evaluation `40 passed`, mobile `26 passed`, TypeScript clean, and
Expo Doctor `21/21`. Gradle produced a standalone Android debug APK (`assembleDebug`, 213 tasks) with
package `com.erena.eatbetter`; ADB installed it on `boyama_test`, and a cold MainActivity launch
completed with a live app process. Automated tests verify draft serialization/restoration and screen
behavior. A physical-device OS interruption pass remains necessary before making a production
reliability claim.

## Scope and environment

- Android SDK emulator `boyama_test`, Expo Go, Expo SDK 57.
- FastAPI local runtime with the real OpenAI vision/canonicalization and USDA providers.
- One previously unused, user-supplied pasta-and-meatballs image.
- Deterministic portion-review and food-choice fixtures.
- Backend, evaluation, and mobile regression suites were green before this exploratory pass.

The unseen image had no weighed ground truth. It was suitable for qualitative visible-food recognition
only, not portion, calorie, hidden-ingredient, or end-to-end nutrition accuracy claims.

## Findings

### EB-QA-001 — P1 — Canonical choices can be indistinguishable

**Observed:** Real recognition returned `spaghetti`, `meatballs`, `tomato sauce`, `Parmesan cheese`,
and `parsley`. USDA retrieval returned five different FDC IDs for each item, but every displayed
candidate had the same label. The user saw five `SPAGHETTI` buttons, five `MEATBALLS` buttons, and so
on. The constrained selector safely abstained on all five items.

**Impact:** The app correctly avoids guessing, but gives the user no information with which to finish
the required review. The live-provider happy path is blocked.

**Expected:** Deduplicate equivalent candidates, prefer appropriate generic/reference foods, and show
distinguishing attributes such as cooked/dry state, data type, brand, or a concise description.

### EB-QA-002 — P1 — Removing an unresolved item leaves a permanent mobile blocker

**Reproduction:** Create an item with a pending identity clarification, then remove that item. The API
marks its clarification `DISMISSED`, but leaves `resolution_satisfied=false`. The mobile client counts
every blocking clarification with `resolution_satisfied=false` without checking status or whether its
item remains active.

**Observed:** The removed `oil` item disappeared, but Today still said `2 quick checks`; reopening the
meal continued to ask `How should we resolve oil?`. The mobile Save button remained disabled.

**Impact:** A normal correction can make a meal impossible to save from the app.

**Expected:** Removal should satisfy/dismiss associated blockers consistently. Mobile blocker
selection should include only pending blockers for active items, matching the domain confirmation
rule.

### EB-QA-003 — P1 — Incomplete meals are presented as saved and cannot be resumed

**Reproduction:** Create a meal but interrupt before attaching an image or completing analysis, then
open Today.

**Observed:** An `UPLOADED` meal with no image appeared as `Meal photo · 0 kcal` without a pending or
failed badge. Opening it showed `Meal saved`, `Review pending`, `Nutrition data: USDA FoodData
Central`, and `Analyzed from your photo`. There was no resume, retry, attach-photo, or discard action.

**Impact:** Cancellation, process death, or an interrupted upload strands misleading records in meal
history.

**Expected:** Render each lifecycle state explicitly. Resume recoverable attempts, offer retry/discard
for failures, and reserve saved/provenance claims for confirmed meals with matching evidence.

### EB-QA-004 — P1 — “None of these” opens an add flow instead of resolving/replacing the item

**Observed:** Choosing `None of these` or `Search manually` opens an editor titled `Add a missing food`
with the original query prefilled. The service behind that editor appends a new item; it does not
replace the unresolved item or resolve its existing clarification.

**Impact:** Following the apparent recovery path can create a duplicate food while leaving the
original blocker in place. The user must discover an additional remove operation to recover.

**Expected:** A manual-search action launched from an identity clarification should replace/resolve
that specific item, or clearly explain and atomically perform any remove-and-add behavior.

### EB-QA-005 — P1 — Food-choice development demo breaks under live-provider configuration

**Reproduction:** Start the app with `NUTRITION_PROVIDER=usda`, open `Open food-choice demo`, and choose
`Cream sauce`.

**Observed:** The answer endpoint returned HTTP 502 with `USDA_INVALID_RESPONSE` because the fixture's
non-numeric candidate identifier was sent to the real USDA adapter. The UI displayed only `Something
went wrong. Please try again.`

**Impact:** The fixture intended for the submission walkthrough is unusable when the app is configured
for real providers.

**Expected:** Fixtures should carry deterministic nutrition snapshots or use fixture-bound adapters,
independent of live-provider configuration.

### EB-QA-006 — P2 — Provider and evidence labels are not truthful

**Observed:** Today displayed `Demo API` whenever `/health` was reachable, even while real OpenAI and
USDA providers were active. Meal Detail always displayed `Nutrition data: USDA FoodData Central` and
`Analyzed from your photo`, including for deterministic fixtures and an incomplete meal with no image.

**Expected:** Derive labels from actual provider/evidence metadata, or use neutral copy when that
metadata is unavailable.

### EB-QA-007 — P2 — A “None” portion remains as an active zero-gram food

**Observed:** Selecting `None · About 0 g` for fixture olive oil produced an active, ready `Olive oil`
card with `0 g · 0 kcal`. The header still counted four foods, Meal Detail listed the zero-gram item,
and the correction count increased.

**Expected:** A semantic `None` answer should remove or exclude the item from active food counts and
saved detail, while preserving the correction in the audit trail.

### EB-QA-008 — P2 — Stable provider failures fall back to generic UI copy

**Observed:** `USDA_INVALID_RESPONSE` reached the mobile client but is absent from `FRIENDLY_ERRORS`, so
the user saw the generic `Something went wrong. Please try again.` message.

**Expected:** Map every documented stable provider error to an actionable message and a retry or
alternate-selection path where appropriate.

### EB-QA-009 — P2 — Canceling an emulator camera capture resets the app to Today

**Observed:** Camera permission, launch, shutter, and preview worked. Canceling the captured frame
showed the app splash and returned to Today instead of the existing Capture screen.

**Impact:** Photo context and capture progress can be lost. This was observed in Expo Go and must be
rechecked in a standalone Android build before assigning production scope.

### EB-QA-010 — P2 — Successful edit/add forms are not closed or reset

**Code-confirmed:** `ReviewScreen` keeps `editor`, `adding`, `query`, and gram input state locally. The
successful `onUpdate` and `onAdd` paths update the meal but never clear those states. The user can see
stale forms or accidentally submit the same addition again.

**Expected:** Close and reset the relevant editor only after a successful mutation; retain it with the
entered data after an error.

### EB-QA-011 — P2 — Review numeric validation permits non-finite and zero-value edge cases

**Code-confirmed:** The regular Change amount and Add food forms check blank/negative values but do not
use `Number.isFinite`, unlike the clarification amount form. Zero grams is accepted for ordinary food
edits/additions and creates active zero-value items.

**Expected:** Require a finite positive amount for ordinary active foods. Treat zero as remove/none
only in flows where that meaning is explicit.

### EB-QA-012 — P2 — Hidden-ingredient wording can invite double counting

**Observed:** The unseen image visibly contained Parmesan, which was already recognized as a food, but
the app later asked `Did this meal include additional cheese?` alongside oil and butter questions.

**Impact:** `Yes` can add a second cheese item without explaining whether the visible topping is
already counted.

**Expected:** Suppress or clarify hidden-ingredient questions that overlap observed foods; explicitly
say `in addition to the visible Parmesan` when that is the intended question.

### EB-QA-013 — P2 — Live analysis has a long undifferentiated wait

**Observed:** Vision completed in approximately 12.7 seconds and the complete five-item analysis in
approximately 24.8 seconds. The UI remained on a generic `Identifying foods` message throughout.

**Expected:** Show truthful staged progress and preserve a recoverable attempt if the user cancels.

### EB-QA-014 — P3 — Loading can display a stale Log meal action

**Observed:** During Today refresh, the loading state sometimes displayed the fixed `Log meal` button
from the previous non-empty meal list.

**Expected:** Decide deliberately whether capture remains available during refresh; do not derive the
loading layout from stale meal state accidentally.

## Passed checks

- Android photo-library picker and local image preview.
- Standards-compliant multipart image upload.
- Real OpenAI image usability and visible-food observation.
- Real USDA connectivity, rate-limit parsing, and food detail retrieval for valid numeric IDs.
- Hidden-ingredient `No` progression.
- Portion option selection, confirmation, deterministic totals, and Today aggregation.
- Resume of an ordinary `NEEDS_REVIEW` meal from Today.
- Confirmed meal reopening and back navigation.
- Camera permission, camera launch, shutter, and captured-frame preview.
- Change-amount mutation and real-provider Add food service calls.
- Unsupported image upload returns stable `UNSUPPORTED_IMAGE`.
- Offline Today and analysis retry states were exercised earlier in the same emulator session.

## Coverage limitations

- No signed release APK, physical Android phone, iOS device, or screen-reader pass.
- No measured ground truth for the unseen photo, so no portion/calorie accuracy score.
- No background/foreground, process-death recovery, slow-network shaping, or concurrent-tap stress.
- Destructive meal-item removal was exercised through the local API; the UI button uses the same
  endpoint, but a full confirmation-dialog usability pass was not performed.

## Remaining validation order

1. Install the standalone build on a physical Android device and exercise camera cancel,
   background/foreground, and process-death restoration.
2. Run an iOS and screen-reader accessibility pass.
3. Collect owned or consented smartphone meals with measured portions for product-specific accuracy.

The same unseen image has been rerun as a P1 regression case. A second unseen owned/consented image
with weighed portions is still required for true end-to-end accuracy evaluation.
