# Multimodal meal recognition

## Responsibility

P4 implements `image → observations`, not `image → calories`. The vision layer describes visible food
components, preparation evidence, optional portion ranges, genuine alternatives, image quality, and
possible hidden ingredients. It cannot emit canonical food IDs, USDA/FDC IDs, calories, or macros.

USDA search and detail retrieval remain the independent P3 boundary. `MealRecognitionService` does not
call them; the unified endpoint invokes P3/P5 afterward through separate services and AI-run stages.
This keeps recognition errors measurable separately from retrieval and selector errors.

## Structured output

The OpenAI adapter uses the Responses API typed parsing interface with `MealObservation` as its strict
Pydantic format. Every nested model forbids extra fields. Required arrays are bounded, observed foods
are capped at 20 for abuse protection, and alternatives are capped at three. Provider refusals,
missing parsed output, and schema incompatibility are failures; there is no natural-language or regex
fallback.

An observation contains:

- image usability and a compact issue enum;
- zero or more observed foods;
- optional integer gram ranges from 0–5000 as a technical sanity bound;
- categorical `HIGH`, `MEDIUM`, or `LOW` observation certainty;
- alternatives, uncertainties, and concise visible evidence;
- possible hidden ingredients with `LOW`, `MATERIAL`, or `UNKNOWN` potential impact.

Certainty is a diagnostic description, not a calibrated probability and not system confidence. A null
portion is preferred when scale evidence is insufficient. An unusable/non-meal image cannot contain
observed foods; an empty but usable plate may contain no foods.

## Hidden ingredients and composite foods

Plausible but unseen oil, butter, cream, dressings, sauces, cheese, nut butter, or syrup stays in the
dedicated hidden-warning collection. It is not promoted to a detected meal item. Recognizable composite
foods remain composite unless their components are visually separable and nutritionally meaningful.
This reduces plausible-recipe hallucinations and preserves evaluation clarity.

## Prompt and injection boundary

The immutable runtime prompt version is `meal_recognition_v4`. It treats the image and optional user
context as untrusted evidence and instructs the model never to follow embedded directions. User context
is limited to 1000 characters by the API schema and is not written to routine recognition logs; only a
presence boolean is logged. Prompt behavior changes require a new versioned file. Every published
Nutrition5k and SNAPMe result was measured under `meal_recognition_v2`; see
[measured evaluation](measured-evaluation.md) for the resulting evidence-version mismatch.

## Private images and reliability

JPEG, PNG, and WebP signatures are validated before storage and again through the provider-neutral
`MealImage` object. Recognition reads bytes from private storage and sends a data URL directly; it does
not publish the image. The OpenAI SDK is pinned at `3.2.0` and its automatic retries are disabled so the
adapter's bounded policy is authoritative.

The default timeout is 30 seconds with at most three attempts. Timeouts, connection failures, 429, and
5xx retry with bounded exponential delay and jitter. Unsupported images, refusals, and invalid schemas
do not retry. Raw provider errors, image bytes, data URLs, request bodies, credentials, auth tokens, and
user context are never logged.

Original meal-image retention remains a privacy-sensitive product decision. P4 does not require
permanent retention and does not automatically delete images while that policy is unresolved.

## Audit and state

Each attempt appends a `MEAL_RECOGNITION` AI run containing the exact provider/model/prompt version,
image detail, reasoning effort, status, timestamps, request ID, latency, actual token usage if returned,
retry count, error code, and validated structured output. Estimated cost remains null because reliable
versioned pricing is not encoded.

Recognition produces pre-canonical items and completes its independent AI run before P5 enrichment.
The unified operation ultimately returns `NEEDS_REVIEW`. Duplicate endpoint calls do not rerun
recognition; P5 may independently retry failed item-level selection.
