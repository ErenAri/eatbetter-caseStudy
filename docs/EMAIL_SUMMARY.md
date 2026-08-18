Subject: EatBetter full-stack case study — confidence-aware meal logging

Hi EatBetter team,

I built a focused Expo + FastAPI meal logger that treats AI output as uncertain observations, grounds
foods in retrieved canonical candidates, calculates nutrition deterministically, and blocks
confirmation until material uncertainty is resolved. The app includes Today, capture, AI review, and
meal detail flows; the backend includes explicit states, idempotency, retries, structured logs,
ownership checks, correction history, and high-value tests.

I intentionally did not add coaching, social, or tracking features. Deterministic fixtures keep local
development reproducible, while OpenAI vision/selection and USDA retrieval adapters are implemented
behind the same interfaces. They were run on a licensed 12-dish Nutrition5k secondary subset with a
frozen three-dish holdout. Development food F1 improved from 0.286 to 0.615 after one isolated
recognition-prompt change. On the tiny holdout, food F1 was 0.353 and the hybrid safely auto-accepted
no meals, but required review for all three and produced no complete nutrition totals. This is
rig-captured case-study evidence—not product or clinical validation. Supabase runtime persistence,
production JWT verification, and an owned/consented phone-photo benchmark remain deferred.

The main trade-off is selective friction: high-impact uncertainty asks a targeted question instead of
silently saving a confident guess.

Best,
[Replace with your name before sending]
