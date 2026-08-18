# P2 database workflow

The committed `supabase/config.toml` initializes the project-scoped CLI configuration. The
authoritative PostgreSQL migration is
`supabase/migrations/001_p2_authoritative_schema.sql`. It targets Supabase Postgres because profiles
reference `auth.users`; no passwords are duplicated in application tables.

## Create and apply locally

Install Docker Desktop and use the Supabase CLI from the repository root:

```powershell
npx supabase start
npx supabase db reset
```

`db reset` recreates local Postgres and applies every version-controlled migration. It is destructive
to local development data.

## Reset local development data

```powershell
npx supabase db reset
```

Private storage objects are outside PostgreSQL. The application deletes the image object before
deleting the meal; database foreign keys then cascade items, candidates, AI runs, corrections, and
clarifications. Operational cleanup should reconcile failed storage deletions before production.

## Apply to a linked non-local project

After reviewing the generated diff and target project:

```powershell
npx supabase db push
```

Do not run this against production from an unreviewed branch. P2 uses an in-memory runtime adapter so
tests do not need a database or external credentials; the migration is the contract for the P2
Postgres repository adapter that follows.
