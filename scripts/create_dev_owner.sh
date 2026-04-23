#!/usr/bin/env bash
# scripts/create_dev_owner.sh
# Provision a fresh owner user in the dev Supabase project.
#
# Creates the user in two steps:
#   1. POST /auth/v1/admin/users (creates the auth.users row with a confirmed email)
#   2. INSERT INTO public.users (creates the matching app-side row with role='owner')
#
# Usage:
#   DEV_SUPABASE_URL='https://<ref>.supabase.co' \
#   DEV_SUPABASE_SECRET_KEY='sb_secret_...' \
#   DEV_DATABASE_URL='postgresql://...?sslmode=require' \
#     ./scripts/create_dev_owner.sh
#
# All three env vars are required. Tip: source them from backend/.env after
# you've already pointed it at dev:
#   set -a; source backend/.env; set +a
#   DEV_SUPABASE_URL="$SUPABASE_URL" \
#     DEV_SUPABASE_SECRET_KEY="$SUPABASE_SECRET_KEY" \
#     DEV_DATABASE_URL='postgresql://...' \
#     ./scripts/create_dev_owner.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/confirm.sh
source "$SCRIPT_DIR/lib/confirm.sh"

# --- 1. Validate env --------------------------------------------------------

: "${DEV_SUPABASE_URL:?DEV_SUPABASE_URL is required (e.g. https://abcd.supabase.co)}"
: "${DEV_SUPABASE_SECRET_KEY:?DEV_SUPABASE_SECRET_KEY is required (sb_secret_...)}"
: "${DEV_DATABASE_URL:?DEV_DATABASE_URL is required (postgresql://...)}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "${RED}ERROR: python3 not found (used for JSON parsing).${RESET}" >&2
    exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
    echo "${RED}ERROR: psql not found.${RESET}" >&2
    exit 1
fi

# Sanity check: the URL host must match the DB host's project ref
URL_REF=$(echo "$DEV_SUPABASE_URL" | sed -n 's|https://\([a-z0-9]*\)\.supabase\.co.*|\1|p')
DB_REF=$(extract_project_ref "$DEV_DATABASE_URL")
if [ -n "$URL_REF" ] && [ -n "$DB_REF" ] && [ "$URL_REF" != "$DB_REF" ]; then
    echo "${RED}ERROR: project ref mismatch between DEV_SUPABASE_URL ($URL_REF) and DEV_DATABASE_URL ($DB_REF).${RESET}" >&2
    exit 1
fi

print_banner "$YELLOW" "Create dev owner -> project: ${URL_REF:-unknown}"
confirm_project_ref "DEV" "${URL_REF:-$DB_REF}"

# --- 2. Prompt for user details ---------------------------------------------

printf "Email: "
read -r EMAIL
if [ -z "$EMAIL" ]; then
    echo "${RED}Email is required.${RESET}" >&2
    exit 1
fi

printf "Full name: "
read -r FULL_NAME
if [ -z "$FULL_NAME" ]; then
    echo "${RED}Full name is required.${RESET}" >&2
    exit 1
fi

printf "Password (input hidden): "
stty -echo
read -r PASSWORD
stty echo
echo
if [ -z "$PASSWORD" ]; then
    echo "${RED}Password is required.${RESET}" >&2
    exit 1
fi

# --- 3. Create the auth user via the Admin API ------------------------------

echo
echo "${BOLD}Step 1/2: creating auth user...${RESET}"

# Build JSON payload safely with python
PAYLOAD=$(EMAIL="$EMAIL" PASSWORD="$PASSWORD" python3 -c '
import json, os
print(json.dumps({
    "email": os.environ["EMAIL"],
    "password": os.environ["PASSWORD"],
    "email_confirm": True,
}))
')

RESPONSE=$(curl -sS -X POST "${DEV_SUPABASE_URL%/}/auth/v1/admin/users" \
    -H "apikey: $DEV_SUPABASE_SECRET_KEY" \
    -H "Authorization: Bearer $DEV_SUPABASE_SECRET_KEY" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

# Parse the response
AUTH_ID=$(RESPONSE="$RESPONSE" python3 -c '
import json, os, sys
try:
    data = json.loads(os.environ["RESPONSE"])
except json.JSONDecodeError:
    sys.stderr.write("Could not parse Auth API response as JSON:\n")
    sys.stderr.write(os.environ["RESPONSE"] + "\n")
    sys.exit(1)
if "id" in data:
    print(data["id"])
else:
    sys.stderr.write("Auth API did not return a user id. Response:\n")
    sys.stderr.write(json.dumps(data, indent=2) + "\n")
    sys.exit(1)
')

if [ -z "$AUTH_ID" ]; then
    echo "${RED}Failed to create auth user.${RESET}" >&2
    exit 1
fi

echo "  auth.users.id = ${BOLD}${AUTH_ID}${RESET}"

# --- 4. Insert the matching public.users row --------------------------------

echo
echo "${BOLD}Step 2/2: inserting public.users row (role=owner)...${RESET}"

PGPASSWORD_NOTE="(connection string includes credentials)"
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 <<SQL
INSERT INTO public.users (auth_id, email, full_name, role, is_active)
VALUES ('${AUTH_ID}', '${EMAIL}', '${FULL_NAME}', 'owner', true);
SQL

print_banner "$GREEN" "DEV OWNER CREATED"
echo "  Email:   $EMAIL"
echo "  Name:    $FULL_NAME"
echo "  Role:    owner"
echo "  auth_id: $AUTH_ID"
echo
echo "Login at the local frontend with these credentials once you've pointed"
echo "backend/.env and frontend/.env at the dev project."
