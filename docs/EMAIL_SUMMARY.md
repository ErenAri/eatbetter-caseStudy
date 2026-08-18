Subject: EatBetter full-stack case study — confidence-aware meal logging

Hi EatBetter team,

I built a focused native Expo + FastAPI meal logger that treats AI output as uncertain observations,
grounds foods in retrieved canonical candidates, calculates nutrition deterministically, and blocks
confirmation until material uncertainty is resolved. The app includes Today, capture, analysis,
review, clarification, confirmation, and meal-detail flows. The backend includes explicit lifecycle
states, idempotency, bounded retries, structured AI-run metadata, ownership checks, correction history,
and deterministic tests.

For measured evidence, I used a licensed 12-dish Nutrition5k subset with a frozen three-dish holdout
and a separate licensed SNAPMe recognition benchmark with 30 development and 10 participant-disjoint
holdout phone photos. On the SNAPMe holdout, all 10 cases completed; strict lexical F1 was 0.371, while
completed one-to-one semantic adjudication produced precision 0.853, recall 0.806, and F1 0.829. This
is recognition-only external evidence—not weighed portion, nutrition, product, clinical, or competitor
validation.

The main trade-off is selective friction: high-impact uncertainty asks a targeted question instead of
silently saving a confident guess. Supabase runtime persistence, production JWT verification, and an
owned/consented weighed phone-photo benchmark remain deferred.

Repository: https://github.com/ErenAri/eatbetter-caseStudy
Walkthrough: [paste Loom link]

I used OpenAI Codex as an implementation and analysis assistant for scaffolding, tests, documentation,
and evaluation tooling. Visible-label and semantic-adjudication decisions were reviewed separately
from model execution, and the repository documents the measured boundaries and unresolved production
work.

Best,
Eren Ari
