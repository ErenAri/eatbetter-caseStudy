Subject: EatBetter full-stack case study — confidence-aware meal logging

Hi EatBetter team,

I built a focused native Expo + FastAPI meal logger that treats AI output as uncertain observations, grounds foods in retrieved canonical candidates, calculates nutrition deterministically, and blocks confirmation until material uncertainty is resolved. The app includes Today, capture, analysis, review, clarification, correction/recovery, confirmation, and meal-detail flows. The backend includes explicit lifecycle states, idempotency, bounded retries, structured AI-run metadata, ownership checks, correction history, and deterministic tests.

For measured evidence, I used two complementary external datasets. SNAPMe provides ordinary phone-photo visible-food recognition evidence: the participant-disjoint 10-photo holdout completed 10/10 cases, and one-to-one semantic adjudication produced precision 0.853, recall 0.806, and F1 0.829. This is recognition-only evidence—not weighed portion, nutrition, product, clinical, or competitor validation.

Nutrition5k provides a small measured secondary end-to-end diagnostic set. The corrected v2 contract retains 9 development and 3 historical secondary holdout IDs from v1; because those three IDs were already observed before v2, I do not present them as a newly untouched holdout. Those experiments exposed retrieval and clarification completion as the main downstream limits.

The main product trade-off is selective friction: high-impact uncertainty asks a targeted question instead of silently saving a confident guess. A controlled v3 vision-prompt experiment was rejected after all three paired F1 repeats regressed, and later artifact-only traces led to a direct `REMOVE_ITEM` recovery for hallucinated candidate-bearing foods rather than benchmark-specific relabeling.

Latest local verification: backend 156 passed, mobile 28/28 passed, and TypeScript is clean. Submission CI also runs backend, evaluation, mobile, and typecheck suites on GitHub.

Supabase runtime persistence, production JWT verification, production object storage/deployment/monitoring, and an owned/consented weighed phone-photo benchmark remain deferred.

Repository: https://github.com/ErenAri/eatbetter-caseStudy
Walkthrough: [paste Loom link]

I used OpenAI Codex as an implementation and analysis assistant for scaffolding, tests, documentation, and evaluation tooling. Human review remained authoritative for visible-food labels, uncertainty exclusions, semantic adjudication, scope decisions, and final submission claims.

Best,
Eren Ari
