#!/usr/bin/env bash
# scripts/backup_prod_db.sh
# Take a pg_dump backup of the production Supabase database.
#
# Prod URL resolution order:
#   1) PROD_DATABASE_URL env var (escape hatch / CI)
#   2) macOS Keychain entry: service "inventorypp_prod_db_url", account "$USER"
#   3) Exit with instructions
#
# Backups land in: <repo>/../inventoryapp_db_backups/
#
# TODO(future): if Supabase Storage buckets are added later, mirror them
# separately via `supabase storage cp` or the S3 API.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$(cd "$REPO_ROOT/.." && pwd)/inventoryapp_db_backups"

# shellcheck source=lib/confirm.sh
source "$SCRIPT_DIR/lib/confirm.sh"

# --- 1. Resolve prod DB URL --------------------------------------------------

PROD_URL="${PROD_DATABASE_URL:-}"

if [ -z "$PROD_URL" ]; then
    if command -v security >/dev/null 2>&1; then
        if PROD_URL=$(security find-generic-password -a "$USER" -s inventorypp_prod_db_url -w 2>/dev/null); then
            : # got it
        else
            PROD_URL=""
        fi
    fi
fi

if [ -z "$PROD_URL" ]; then
    cat >&2 <<EOF
${RED}ERROR: could not resolve the prod DB URL.${RESET}

Either export PROD_DATABASE_URL in your shell, or store it once in macOS Keychain:

    security add-generic-password -a "\$USER" -s inventorypp_prod_db_url -w

When prompted, paste the URI from Supabase dashboard:
    Project Settings -> Database -> Connection string -> URI

Make sure:
  - port is 5432 (NOT the pooler port 6543)
  - ?sslmode=require is appended

Then re-run this script.
EOF
    exit 1
fi

# --- 2. Confirm we're hitting the right project ------------------------------

PROJECT_REF=$(extract_project_ref "$PROD_URL")
print_banner "$RED" "[PROD BACKUP] target project: ${PROJECT_REF}"
confirm_project_ref "PRODUCTION" "$PROJECT_REF"

# --- 3. Prepare backup directory ---------------------------------------------

mkdir -p "$BACKUP_DIR"
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
DUMP_FILE="$BACKUP_DIR/prod_${TS}.dump"
SCHEMA_FILE="$BACKUP_DIR/prod_${TS}_schema.sql.gz"
ROWCOUNT_FILE="$BACKUP_DIR/prod_${TS}.rowcounts.txt"

echo "Backup destination: $BACKUP_DIR"
echo "Timestamp: $TS"
echo

# --- 4. Custom-format dump (the canonical backup, restorable via pg_restore) -

echo "${BOLD}Step 1/3: pg_dump custom format (-Fc)${RESET}"
pg_dump \
    -Fc \
    --no-owner \
    --no-acl \
    --no-privileges \
    --schema=public \
    --file="$DUMP_FILE" \
    "$PROD_URL"
echo "  -> $(basename "$DUMP_FILE") ($(du -h "$DUMP_FILE" | cut -f1))"
echo

# --- 5. Plain SQL schema snapshot (gzipped, human-readable) ------------------

echo "${BOLD}Step 2/3: schema-only plain SQL snapshot${RESET}"
pg_dump \
    --schema-only \
    --schema=public \
    --no-owner \
    --no-acl \
    "$PROD_URL" \
    | gzip > "$SCHEMA_FILE"
echo "  -> $(basename "$SCHEMA_FILE") ($(du -h "$SCHEMA_FILE" | cut -f1))"
echo

# --- 6. Row counts summary ---------------------------------------------------

echo "${BOLD}Step 3/3: row counts summary${RESET}"
psql "$PROD_URL" -A -F $'\t' -c "
SELECT schemaname, relname, n_live_tup
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;
" > "$ROWCOUNT_FILE"
echo "  -> $(basename "$ROWCOUNT_FILE")"
echo

# --- 7. Summary --------------------------------------------------------------

print_banner "$GREEN" "BACKUP COMPLETE"
echo "Files written to ${BOLD}${BACKUP_DIR}${RESET}:"
ls -lh "$DUMP_FILE" "$SCHEMA_FILE" "$ROWCOUNT_FILE"
echo
echo "Top tables by row count:"
head -10 "$ROWCOUNT_FILE" | column -t -s $'\t' || head -10 "$ROWCOUNT_FILE"
echo
echo "${GREEN}To restore this backup into a dev DB, run:${RESET}"
echo "  DEV_DATABASE_URL='...' DEV_PROJECT_REF='...' \\"
echo "    ./scripts/restore_to_dev.sh '$DUMP_FILE'"
