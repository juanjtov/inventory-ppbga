# scripts/

Operational scripts for backing up the production Supabase database, applying
migrations, restoring backups into the dev project, and provisioning dev users.

All scripts are POSIX-ish bash with `set -euo pipefail`. They print colored
banners and require explicit confirmations before any destructive operation.

## Prerequisites

- **PostgreSQL client tools** (`pg_dump`, `pg_restore`, `psql`) — version 14+.
  Installed via Homebrew: `brew install libpq` or `brew install postgresql@17`.
- **Supabase CLI** — `brew install supabase/tap/supabase`. Optional for these
  scripts (we use raw `pg_dump` for the canonical backup format), but useful
  for ad-hoc inspection: `supabase db dump --db-url '...'`.
- **macOS Keychain** (for `backup_prod_db.sh`) — built into macOS, no install.
- **python3** (for `create_dev_owner.sh`) — used for JSON parsing.

## One-time setup: store the prod DB URL in macOS Keychain

The backup script reads the prod connection string from macOS Keychain. Store
it once and forget it:

```bash
# Run this once. The -w with no value triggers an interactive prompt so the
# URL never appears in your shell history.
security add-generic-password -a "$USER" -s inventorypp_prod_db_url -w
```

When prompted, paste the **full URI** from the Supabase dashboard:

> Project Settings → Database → Connection string → URI

Make sure:
- The host is `db.<projectref>.supabase.co:5432` (port **5432**, NOT the pooler
  port 6543 — pg_dump does not work through the connection pooler).
- `?sslmode=require` is appended to the URL.

Sanity check (will prompt for your Mac password the first time, then offer
"Always Allow"):

```bash
security find-generic-password -a "$USER" -s inventorypp_prod_db_url -w
```

To rotate or delete:

```bash
security delete-generic-password -a "$USER" -s inventorypp_prod_db_url
security add-generic-password   -a "$USER" -s inventorypp_prod_db_url -w
```

The connection string lives **only** in the encrypted Keychain blob. It is
never written to a `.env` file, never exported to your shell, and never
persists outside the backup script's process.

## Scripts

### `backup_prod_db.sh` — back up production

```bash
./scripts/backup_prod_db.sh
```

What it does:

1. Resolves the prod URL: `PROD_DATABASE_URL` env var first, then macOS Keychain.
2. Prompts you to type the project ref to confirm.
3. Writes three files to `../inventoryapp_db_backups/`:
   - `prod_<ts>.dump` — `pg_dump -Fc` custom format (the canonical, restorable backup)
   - `prod_<ts>_schema.sql.gz` — gzipped plain-SQL schema snapshot for human inspection
   - `prod_<ts>.rowcounts.txt` — row counts per table from `pg_stat_user_tables`

The dumps are scoped to the `public` schema so `auth.*` and `vault.*`
permission errors don't pollute the backup.

`pg_dump` uses `REPEATABLE READ` and produces a consistent snapshot without
blocking writes — safe to run against live prod.

### `apply_migrations.sh` — bring a target DB up to current schema

```bash
TARGET_DATABASE_URL='postgresql://postgres:pwd@db.<ref>.supabase.co:5432/postgres?sslmode=require' \
  ./scripts/apply_migrations.sh
```

Iterates `supabase/migrations/*.sql` in lexical order and runs each via
`psql -v ON_ERROR_STOP=1`. Use this on a freshly created dev DB to set up
schema, RLS, indexes, and the realtime publication.

### `restore_to_dev.sh` — restore a prod backup into dev

```bash
DEV_DATABASE_URL='postgresql://postgres:pwd@db.<dev-ref>.supabase.co:5432/postgres?sslmode=require' \
DEV_PROJECT_REF='<dev-ref>' \
  ./scripts/restore_to_dev.sh                              # uses newest backup
# or
  ./scripts/restore_to_dev.sh ../inventoryapp_db_backups/prod_2026-04-08T14-32-05Z.dump
```

Safety nets in this order:

1. Both `DEV_DATABASE_URL` and `DEV_PROJECT_REF` must be set.
2. `DEV_PROJECT_REF` must appear in `DEV_DATABASE_URL`.
3. URL must not match any blacklisted prod ref (`PROD_REF_BLACKLIST` array at
   the top of the script — populate this once with your prod project ref).
4. Operator must type the dev project ref.
5. Operator must type the literal phrase `restore to dev`.

The restore excludes `public.users` (Option A: cross-project auth migration is
brittle, so dev gets a fresh owner via `create_dev_owner.sh`).

### `create_dev_owner.sh` — provision the dev owner

```bash
DEV_SUPABASE_URL='https://<dev-ref>.supabase.co' \
DEV_SUPABASE_SECRET_KEY='sb_secret_...' \
DEV_DATABASE_URL='postgresql://postgres:pwd@db.<dev-ref>.supabase.co:5432/postgres?sslmode=require' \
  ./scripts/create_dev_owner.sh
```

Two-step provisioning:

1. POST `/auth/v1/admin/users` to create the Supabase Auth user (with
   `email_confirm: true` so login works immediately).
2. `INSERT INTO public.users` with the returned auth UUID and `role='owner'`.

Use a non-production email so there's never any confusion about which env
you're operating in (e.g. `dev-owner@example.test`).

## Day-to-day workflow

```text
First time:
  1. brew install supabase/tap/supabase libpq
  2. Store prod URL in Keychain
  3. ./scripts/backup_prod_db.sh
  4. Create inventorypp-dev project in Supabase dashboard
  5. TARGET_DATABASE_URL='<dev>' ./scripts/apply_migrations.sh
  6. DEV_DATABASE_URL='<dev>' DEV_PROJECT_REF='<ref>' \
       ./scripts/restore_to_dev.sh
  7. DEV_SUPABASE_URL='<dev>' DEV_SUPABASE_SECRET_KEY='<sb_secret>' \
     DEV_DATABASE_URL='<dev>' \
       ./scripts/create_dev_owner.sh
  8. Edit backend/.env and frontend/.env to point at dev

Routine:
  - Take a fresh prod backup before any risky migration:
      ./scripts/backup_prod_db.sh
  - Refresh dev with the latest prod data when needed:
      DEV_DATABASE_URL=... DEV_PROJECT_REF=... ./scripts/restore_to_dev.sh
  - Apply a new migration to dev:
      TARGET_DATABASE_URL=<dev> ./scripts/apply_migrations.sh
    Verify, then run the same against prod (paste from Supabase SQL editor or
    rerun apply_migrations.sh with TARGET_DATABASE_URL=<prod>).
```

## TODO (future work)

- Automated nightly backups via `launchd` or cron (currently manual).
- Storage bucket backup (no buckets in use today).
- Migrate to `supabase db push` if the migration count grows past ~10.
- PII scrubbing of restored dev data if real customer data ever lands in
  fiados/sales (today the restore already excludes `public.users`).
