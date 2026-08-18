Subject: EatBetter full-stack case study — confidence-aware meal logging

Hi EatBetter team,

I built a focused Expo + FastAPI meal logger that treats AI output as uncertain observations, grounds
foods in retrieved canonical candidates, calculates nutrition deterministically, and blocks
confirmation until material uncertainty is resolved. The app includes Today, capture, AI review, and
meal detail flows; the backend includes explicit states, idempotency, retries, structured logs,
ownership checks, correction history, and high-value tests.

I intentionally did not add coaching, social, or tracking features. Deterministic fixtures keep local
development reproducible, while OpenAI vision/selection and USDA retrieval adapters are implemented
behind the same interfaces. They have not been run as an accuracy benchmark because this repository
contains neither private live credentials nor a consented labeled meal dataset. Supabase runtime
persistence and production JWT verification remain deferred. I did not fabricate accuracy metrics—the
baseline/hybrid report remains “Not measured yet” until a real development/holdout dataset is run.

The main trade-off is selective friction: high-impact uncertainty asks a targeted question instead of
silently saving a confident guess.

Best,
[Replace with your name before sending]
