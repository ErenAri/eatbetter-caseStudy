# Security and privacy

## Supported status

This is an undeployed case-study repository, not a supported production service. The local bearer-token
path and in-memory adapters are development fixtures.

## Reporting

Do not place vulnerabilities, API keys, access tokens, Supabase credentials, private meal photos, or
personal context in a public issue. Contact the repository owner privately through the GitHub account
that owns this repository and provide only the minimum reproduction data required.

## Sensitive-data boundaries

- Server credentials belong in ignored `.env` files or a deployment secret manager.
- `SUPABASE_SERVICE_ROLE_KEY` must never be exposed to the Expo bundle.
- `EXPO_PUBLIC_*` values are public by design and must not contain secrets.
- Real evaluation images and labels belong under ignored `evals/private/`.
- Raw benchmark run directories are ignored; publish only manually reviewed aggregate reports.
- Development bearer tokens are not production authentication.

If a secret is committed, revoke and rotate it immediately; deleting the file in a later commit does
not remove it from Git history.
