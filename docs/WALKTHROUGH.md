# Suggested 7-minute Loom walkthrough

## 0:00–0:40 — Problem and thesis

- Open with the failure mode: a confident wrong food or portion silently corrupts nutrition totals.
- State the thesis: AI produces observations and uncertainty; retrieval, deterministic nutrition, and targeted human review remain authoritative.
- Make the claim boundary explicit: this is a safer accuracy workflow, not measured superiority to EatBetter or clinical validation.

## 0:40–2:20 — Native mobile demonstration

- Show Today → Capture and select or take a meal photo.
- Add optional context and start analysis.
- On Review, show visible foods, a blocking clarification, food replacement/search, direct remove recovery, and portion correction.
- Point out that the app does not expose raw model confidence; it asks actionable questions instead.
- Resolve the blocker, save the meal, and open Meal Detail.
- Explain that the mobile client displays backend nutrition and never recalculates it.

## 2:20–3:35 — Accuracy and grounding architecture

- Show `meal_recognition_v2` and the strict observation schema.
- Explain constrained canonicalization: the selector receives ranked allowlisted candidate descriptions and may select only a supplied rank or abstain; it does not receive FDC IDs or nutrition.
- Explain that the server validates the selected rank, performs USDA detail lookup, snapshots nutrition, and calculates totals deterministically with Decimal arithmetic.
- Explain that hidden ingredients and unsupported preparation details are not invented as facts.

## 3:35–4:25 — Reliability and observability

- Show meal lifecycle states, ownership checks, idempotent create/request IDs, bounded retries, and stable error contracts.
- Mention structured request logs and AI-run metadata: provider, model, prompt version, latency, token usage, status, and error attribution.
- State the production boundary: runtime persistence, production JWT verification, object storage, deployment, and monitoring sink are deferred; staging/production startup fails closed until the required adapters exist.

## 4:25–5:55 — Measured evidence and iteration

- **SNAPMe phone photos:** 30 development and 10 participant-disjoint holdout photos. The holdout completed 10/10 cases. Strict lexical F1 was 0.371; completed one-to-one semantic adjudication produced precision 0.853, recall 0.806, and F1 0.829.
- State the boundary immediately: SNAPMe supports visible-food recognition only. It does not provide weighed portion, hidden-ingredient, nutrition, USDA-selection, or end-to-end product validation.
- **Nutrition5k secondary evidence:** 12 rig-captured dishes. The corrected v2 contract retains 9 development and 3 historical secondary holdout IDs from v1. Those three IDs were already observed before v2 and are **not** claimed as a newly untouched holdout.
- Historical three-dish secondary results include food F1 0.353 and USDA Recall@5 0.333; hybrid auto-accepted no meals and required review on all three.
- Show the experiment/decision table in the README: v2 recognition accepted, v3 prompt rejected after all 3 paired F1 repeats regressed, hidden routing diagnosed instead of guessed, and clarification trace led to the direct `REMOVE_ITEM` recovery.

## 5:55–6:30 — Biggest trade-off

- Selective friction: ask when unresolved uncertainty can materially change calories or identity instead of optimizing for zero taps.
- The current 100 kcal / 20% thresholds are configurable engineering hypotheses, not clinically calibrated probabilities.
- Explain that the system can be safer while still having poor completion UX; those are separate metrics.

## 6:30–7:00 — Next three improvements

1. Collect owned or consented ordinary phone meals with kitchen-scale portions and measured oil/sauce.
2. Improve USDA retrieval using new development evidence while keeping inspected cases frozen; create a genuinely unseen final holdout.
3. Measure clarification completion/user burden versus unsafe auto-accept on a larger representative set, then implement production auth/persistence/storage/monitoring before deployment.

Close with: the project demonstrates a measured, recoverable meal-logging accuracy workflow—not clinical validity or a numerical “better than EatBetter” claim.
