# Suggested 7-minute Loom walkthrough

## 0:00–0:40 — Problem and thesis

- Open with the failure mode: a confident wrong food or portion silently corrupts nutrition totals.
- State the thesis: AI produces observations and uncertainty; retrieval, deterministic nutrition, and
  targeted human review remain authoritative.

## 0:40–2:20 — Native mobile demonstration

- Show Today → Capture and select a meal photo.
- Add optional context and start analysis.
- On Review, point out visible foods, uncertainty, canonical candidates, portion ranges, and blocking
  clarification rather than raw model confidence.
- Correct one item, answer one clarification, confirm the meal, and open Meal Detail.
- Explain that the mobile client displays backend nutrition and never recalculates it.

## 2:20–3:35 — Accuracy and grounding architecture

- Show the versioned recognition prompt and structured observation schema.
- Explain constrained canonicalization: the selector receives ranked, allowlisted USDA candidate
  descriptions and may select only a supplied rank or abstain.
- Explain deterministic USDA detail parsing and Decimal-based nutrition calculations.
- Emphasize that hidden ingredients and unsupported preparation details are not invented.

## 3:35–4:25 — Reliability and observability

- Show meal lifecycle states, ownership checks, idempotent create/request IDs, bounded retries, and
  stable error contracts.
- Mention structured AI-run metadata: provider, model, prompt version, latency, token usage, status,
  and error attribution.
- State the production boundary: runtime persistence and production JWT verification are deferred.

## 4:25–5:50 — Measured evidence

- Nutrition5k: 12 rig-captured dishes, nine development and three frozen holdout. Holdout food F1 was
  0.353 and USDA Recall@5 was 0.333; the hybrid safely auto-accepted no meals but required review for
  all three.
- SNAPMe: 30 development and 10 participant-disjoint holdout phone photos. The frozen phone-photo
  holdout completed 10/10 cases. Strict lexical F1 was 0.371; completed one-to-one semantic
  adjudication produced precision 0.853, recall 0.806, and F1 0.829.
- State the boundary clearly: SNAPMe supports visible-food recognition only. It does not provide
  weighed portion, hidden-ingredient, nutrition, USDA-selection, or end-to-end product validation.

## 5:50–6:30 — Biggest trade-off

- Selective friction: the system asks a question when unresolved uncertainty can materially change
  calories or food identity instead of optimizing for zero taps.
- The current 100 kcal / 20% thresholds are configurable hypotheses, not clinically calibrated rules.

## 6:30–7:00 — Next three improvements

1. Collect owned or consented phone meals with weighed portions and measured oil/sauce.
2. Improve USDA retrieval using verified misses while keeping the inspected holdouts frozen.
3. Make clarification options more resolvable and measure completion versus unsafe auto-accept.

Close by saying the project demonstrates a safer accuracy workflow, not measured superiority over
EatBetter or clinical validity.
