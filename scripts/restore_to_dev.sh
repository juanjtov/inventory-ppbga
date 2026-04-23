#!/usr/bin/env bash
# scripts/restore_to_dev.sh
# Restore a prod backup .dump into the dev Supabase project.
#
# This is the highest-risk script in the repo. It has multiple safety nets:
#   1. Requires DEV_DATABASE_URL and DEV_PROJECT_REF.
#   2. Asserts DEV_PROJECT_REF is a substring of DEV_DATABASE_URL.
#   3. Refuses if the URL contains any known PROD ref (PROD_REF_BLACKLIST).
#   4. Prompts the operator to type the dev project ref.
#   5. Requires the operator to type the phrase 'restore to dev'.
#
# The public.users table is excluded from the restore so the dev DB starts
# with a fresh, dev-only owner (auth.users is project-scoped and not portable
# across Supabase projects).
#
# Usage:
#   DEV_DATABASE_URL='postgresql://...?sslmode=require' \
#   DEV_PROJECT_REF='abcdefgh' \
#     ./scripts/restore_to_dev.sh [path/to/prod_*.dump]
#
# If no dump path is given, the most recent prod_*.dump in
# ../inventoryapp_db_backups/ is selected.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$(cd "$REPO_ROOT/.." && pwd)/inventoryapp_db_backups"

# shellcheck source=lib/confirm.sh
source "$SCRIPT_DIR/lib/confirm.sh"

# --- BLACKLIST: project refs that must NEVER be restored to ------------------
# Populate this once with your prod project ref(s). Defense-in-depth: even if
# DEV_DATABASE_URL is wrong, the script refuses if it contains any of these.
PROD_REF_BLACKLIST=(
    # "your-prod-ref-here"
)

# --- 1. Validate env --------------------------------------------------------

if [ -z "${DEV_DATABASE_URL:-}" ]; then
    echo "${RED}ERROR: DEV_DATABASE_URL is not set.${RESET}" >&2
    exit 1
fi

if [ -z "${DEV_PROJECT_REF:-}" ]; then
    echo "${RED}ERROR: DEV_PROJECT_REF is not set.${RESET}" >&2
    echo "This is the project ref of the DEV Supabase project (e.g. 'abcdefgh')." >&2
    exit 1
fi

# Check that DEV_PROJECT_REF is actually present in the URL
if ! echo "$DEV_DATABASE_URL" | grep -q "$DEV_PROJECT_REF"; then
    echo "${RED}ERROR: DEV_PROJECT_REF ('$DEV_PROJECT_REF') does not appear in DEV_DATABASE_URL.${RESET}" >&2
    echo "${RED}This usually means the env vars are mismatched. Aborting for safety.${RESET}" >&2
    exit 1
fi

# Refuse if URL matches any blacklisted prod ref
for ref in "${PROD_REF_BLACKLIST[@]}"; do
    if [ -n "$ref" ] && echo "$DEV_DATABASE_URL" | grep -q "$ref"; then
        echo "${RED}ERROR: DEV_DATABASE_URL contains a blacklisted PROD project ref ('$ref').${RESET}" >&2
        echo "${RED}Refusing to restore to a production database.${RESET}" >&2
        exit 1
    fi
done

# Cross-check: extracted ref must equal DEV_PROJECT_REF
EXTRACTED_REF=$(extract_project_ref "$DEV_DATABASE_URL")
if [ "$EXTRACTED_REF" != "$DEV_PROJECT_REF" ]; then
    echo "${RED}ERROR: project ref extracted from URL ('$EXTRACTED_REF') != DEV_PROJECT_REF ('$DEV_PROJECT_REF').${RESET}" >&2
    exit 1
fi

# --- 2. Resolve dump file ----------------------------------------------------

DUMP_FILE="${1:-}"
if [ -z "$DUMP_FILE" ]; then
    DUMP_FILE=$(ls -1t "$BACKUP_DIR"/prod_*.dump 2>/dev/null | head -1 || true)
    if [ -z "$DUMP_FILE" ]; then
        echo "${RED}ERROR: no prod_*.dump found in $BACKUP_DIR.${RESET}" >&2
        echo "Pass the dump file path as the first argument." >&2
        exit 1
    fi
fi

if [ ! -f "$DUMP_FILE" ]; then
    echo "${RED}ERROR: dump file not found: $DUMP_FILE${RESET}" >&2
    exit 1
fi

# --- 3. Print plan + double confirmation -------------------------------------

print_banner "$YELLOW" "RESTORE TO DEV"
echo "  Dump file:    $DUMP_FILE"
echo "  Dump size:    $(du -h "$DUMP_FILE" | cut -f1)"
echo "  Dump mtime:   $(stat -f '%Sm' "$DUMP_FILE" 2>/dev/null || stat -c '%y' "$DUMP_FILE")"
echo "  Target ref:   ${BOLD}${DEV_PROJECT_REF}${RESET}"
echo "  Excluding:    public.users (Option A: fresh dev owner)"
echo

confirm_project_ref "DEV" "$DEV_PROJECT_REF"
confirm_phrase "restore to dev"

# --- 4. Restore --------------------------------------------------------------

echo
echo "${BOLD}Running pg_restore...${RESET}"
pg_restore \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    --schema=public \
    --exclude-table=users \
    -d "$DEV_DATABASE_URL" \
    "$DUMP_FILE"

print_banner "$GREEN" "RESTORE COMPLETE"
echo "Next: create a fresh dev owner with"
echo "  ./scripts/create_dev_owner.sh"
