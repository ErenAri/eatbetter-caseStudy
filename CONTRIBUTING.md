# Contributing

This repository is a case study with deliberately narrow scope. Keep changes aligned with meal capture,
canonical grounding, uncertainty review, evaluation, reliability, or documentation.

## Local checks

Backend and evaluation:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
cd ..
.\backend\.venv\Scripts\python.exe -m pytest evals/tests -q -p no:cacheprovider
```

Mobile:

```powershell
cd mobile
npm test
npm run typecheck
npx expo-doctor
```

## Data and secret policy

Never commit API keys, `.env` files, service-role credentials, meal photos, private manifests, or raw
benchmark outputs. Do not turn demo-provider output into an accuracy claim. Canonical ground truth must
be independently reviewed; the production selection cannot label itself.

For prompt changes, add a new version rather than overwriting an evaluated prompt. Do not tune on the
holdout. Document test commands and any known limitation in the change description.
