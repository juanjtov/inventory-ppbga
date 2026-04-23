#!/usr/bin/env bash
# scripts/apply_migrations.sh
# Apply all SQL migrations in supabase/migrations/ against TARGET_DATABASE_URL.
#
# Usage:
#   TARGET_DATABASE_URL='postgresql://...?sslmode=require' \
#     ./scripts/apply_migrations.sh
#
# This is a tiny runner for the existing manual workflow. It runs each .sql
# file in lexical order via psql with ON_ERROR_STOP, so a failure halts the
# whole batch instead of leaving the DB partially migrated.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$REPO_ROOT/supabase/migrations"

# shellcheck source=lib/confirm.sh
source "$SCRIPT_DIR/lib/confirm.sh"

if [ -z "${TARGET_DATABASE_URL:-}" ]; then
    echo "${RED}ERROR: TARGET_DATABASE_URL is not set.${RESET}" >&2
    echo "Usage:" >&2
    echo "  TARGET_DATABASE_URL='postgresql://...?sslmode=require' $0" >&2
    exit 1
fi

if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "${RED}ERROR: migrations dir not found at $MIGRATIONS_DIR${RESET}" >&2
    exit 1
fi

PROJECT_REF=$(extract_project_ref "$TARGET_DATABASE_URL")
print_banner "$YELLOW" "Apply migrations -> project: ${PROJECT_REF:-unknown}"
confirm_project_ref "TARGET" "$PROJECT_REF"

shopt -s nullglob
MIGRATIONS=("$MIGRATIONS_DIR"/*.sql)
shopt -u nullglob

if [ ${#MIGRATIONS[@]} -eq 0 ]; then
    echo "${YELLOW}No .sql files in $MIGRATIONS_DIR. Nothing to apply.${RESET}"
    exit 0
fi

echo "Found ${#MIGRATIONS[@]} migration(s):"
for f in "${MIGRATIONS[@]}"; do
    echo "  - $(basename "$f")"
done
echo

for f in "${MIGRATIONS[@]}"; do
    echo "${BOLD}Applying $(basename "$f")${RESET}"
    psql "$TARGET_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
    echo "  ${GREEN}ok${RESET}"
    echo
done

print_banner "$GREEN" "MIGRATIONS APPLIED"
