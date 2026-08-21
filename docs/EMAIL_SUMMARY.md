Subject: EatBetter full-stack case study — confidence-aware meal logging

Hi EatBetter team,

I built a focused native Expo + FastAPI meal logger that treats AI output as uncertain observations, grounds foods in retrieved canonical candidates, calculates nutrition deterministically, and blocks confirmation until material uncertainty is resolved. The app includes Today, capture, analysis, review, clarification, correction/recovery, confirmation, and meal-detail flows. The backend includes explicit lifecycle states, idempotency, bounded retries, structured AI-run metadata, ownership checks, correction history, and deterministic tests.

For measured evidence, I used two complementary external datasets. SNAPMe provides ordinary phone-photo visible-food recognition evidence: the participant-disjoint 10-photo holdout completed 10/10 cases, and one-to-one semantic adjudication produced precision 0.853, recall 0.806, and F1 0.829. This is recognition-only evidence—not weighed portion, nutrition, product, clinical, or competitor validation.

Nutrition5k provides a small measured secondary end-to-end diagnostic set. The corrected v2 contract retains 9 development and 3 historical secondary holdout IDs from v1; because those three IDs were already observed before v2, I do not present them as a newly untouched holdout. Those experiments exposed retrieval and clarification completion as the main downstream limits.

The main product trade-off is selective friction: high-impact uncertainty asks a targeted question instead of silently saving a confident guess. Getting that boundary right is where most of the engineering went — a controlled v3 vision-prompt experiment was rejected after all three paired F1 repeats regressed, and a relative-uncertainty threshold that interrupted users about a 7-calorie garnish now requires the absolute calorie swing to clear a floor as well.

The repository also contains a second, selectable nutrition path (`NUTRITION_PROVIDER=ai`) that resolves nutrition from the model alone, refuses foods it does not recognise rather than inventing a value, and marks its output `AI_ESTIMATE`. It exists because USDA has no entry for regional dishes such as lahmacun or Adana kebab. It has unit tests and **no accuracy measurement**, and none of the numbers above describe it.

Against EatBetter specifically: the improvement I claim is that this design refuses rather than guesses, and interrupts in proportion to calorie impact rather than model doubt. I have run no head-to-head benchmark and claim no numerical comparison. The README section “Compared to EatBetter” states the position, the protocol that would settle it (weighed photos through both apps, primary metric being unsafe auto-accept rate), and the failure cases from my own runs that motivate it.

Latest local verification: backend 236 passed, mobile 35/35 passed, and TypeScript is clean. Submission CI also runs backend, evaluation, mobile, and typecheck suites on GitHub.

Supabase runtime persistence, production JWT verification, production object storage/deployment/monitoring, and an owned/consented weighed phone-photo benchmark remain deferred.

Next steps, in the order I would take them:

1. Fix USDA retrieval query construction. The full observed phrase is sent as the search query, so modifiers outweigh head nouns — "stir-fried noodles" retrieves mushrooms. Retrieving on the head noun and re-ranking against the full phrase is the cheapest testable hypothesis, and it is measurable on the existing development split.
2. Ask portion questions in units a person can answer. Zero of five holdout clarifications were resolvable from ground truth, and I believe the unit is the reason: nobody knows what 180 g of kebab looks like, but everyone can answer "one skewer or two".
3. Measure the AI nutrition path against Nutrition5k development, so the choice between it and USDA becomes a measured decision rather than an assumed one.

Repository: https://github.com/ErenAri/eatbetter-caseStudy
Walkthrough: https://www.loom.com/share/1bf1d0fa97f74efaaf380602d4f33d55

I used two AI assistants and both are disclosed in the README: OpenAI Codex for scaffolding, tests, documentation, and evaluation tooling across the bulk of the build, and Claude in a later session for the AI nutrition path, the uncertainty gates, and several mobile fixes. Human review remained authoritative for visible-food labels, uncertainty exclusions, semantic adjudication, scope decisions, and final submission claims. No published number was produced by an assistant grading its own output.

Best,
Eren Ari
