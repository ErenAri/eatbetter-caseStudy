# Mobile meal logging UX

## Screen flow

```text
Today → Capture → Analysis → Review → Confirm → Meal detail
```

`App.tsx` retains the existing lightweight route-state approach. Beginning capture creates one
`meal_request_id`; upload and analysis retries reuse the same request and meal IDs. The analysis screen
uses indeterminate, coarse explanatory copy rather than invented percentages. A failed request keeps
the selected photo and offers retry or a new-photo path.

## Review philosophy

The interface does not expose raw model confidence. Instead, it converts uncertainty into actionable
review only when the backend determines that the uncertainty can materially affect the meal result.
Resolved foods say “Looks good.” The first unresolved backend clarification is rendered prominently,
without reordering P6 priority. Nutrition appears only when the backend returns final item nutrition.

`ClarificationCard` is the single typed renderer for canonical selection, portion, hidden ingredient,
and unresolved identity questions. It submits stored option IDs or explicit custom grams; it never
parses labels, converts household volume, or calculates nutrition. All mutations replace local state
with the returned authoritative meal.

## Backend interaction

The centralized client covers create, private image upload, analysis, meal/list/daily-summary reads,
clarification answers, item correction/removal/addition, and confirmation. Friendly copy maps stable
backend failures without showing model/provider internals. If confirmation reports unresolved state,
the app refetches the meal and remains on Review.

The smallest supported missing-food/manual-search path asks for a food query and grams, then uses the
existing add-item endpoint. Changing an existing food is limited to its already retrieved candidates;
there is no standalone public food-search endpoint yet.

## Camera and images

Expo Image Picker launches the native rear camera or photo library. Camera denial offers system
settings and photo-library alternatives. Images use quality `0.8`, balancing upload size and visual
evidence quality, and are deliberately previewed before analysis. The app does not log local image
URIs or claim an image-retention behavior the backend does not implement.

## Deterministic demos

Local/test backends expose two development-only flows:

- Portion review: chicken, rice, broccoli, and oil via `/dev/fixtures/review-meal`.
- Canonical ambiguity: creamy sauce choices via `/dev/fixtures/canonical-review-meal`; selecting a
  candidate grounds it and leads to deterministic portion reassessment.

The normal demo-provider photo flow also produces chicken, rice, broccoli, and a material cooking-oil
presence clarification. The UI labels fixture access as development demo data.

## Remaining production work

Production Supabase/JWT authentication, persistent route restoration across process death, a dedicated
manual USDA search endpoint, and a selected analytics provider remain deferred.
