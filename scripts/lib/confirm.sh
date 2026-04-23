#!/usr/bin/env bash
# scripts/lib/confirm.sh
# Shared safety helpers for destructive DB operations.
# Source this file from other scripts: `source "$(dirname "$0")/lib/confirm.sh"`

# ANSI colors (no-op when stdout is not a TTY)
if [ -t 1 ]; then
    RED=$'\033[0;31m'
    YELLOW=$'\033[0;33m'
    GREEN=$'\033[0;32m'
    BOLD=$'\033[1m'
    RESET=$'\033[0m'
else
    RED=""
    YELLOW=""
    GREEN=""
    BOLD=""
    RESET=""
fi

# extract_project_ref <postgres_url>
# Pulls the Supabase project ref out of a connection string like:
#   postgresql://postgres:pwd@db.<ref>.supabase.co:5432/postgres
# Prints the ref to stdout, or empty if not matched.
extract_project_ref() {
    local url="$1"
    # Match db.<ref>.supabase.co
    local ref
    ref=$(echo "$url" | sed -n 's/.*db\.\([a-z0-9]*\)\.supabase\.co.*/\1/p')
    echo "$ref"
}

# print_banner <color> <label>
print_banner() {
    local color="$1"
    local label="$2"
    echo
    echo "${color}${BOLD}================================================================${RESET}"
    echo "${color}${BOLD}  ${label}${RESET}"
    echo "${color}${BOLD}================================================================${RESET}"
    echo
}

# confirm_project_ref <env_label> <expected_ref>
# Prompts the operator to type the project ref. Aborts the script on mismatch.
confirm_project_ref() {
    local env_label="$1"
    local expected="$2"

    if [ -z "$expected" ]; then
        echo "${RED}ERROR: could not extract project ref from URL${RESET}" >&2
        exit 1
    fi

    echo "${YELLOW}You are about to operate on the ${BOLD}${env_label}${RESET}${YELLOW} Supabase project.${RESET}"
    echo "${YELLOW}Project ref: ${BOLD}${expected}${RESET}"
    echo
    printf "Type the project ref to confirm: "
    read -r typed

    if [ "$typed" != "$expected" ]; then
        echo "${RED}Project ref mismatch (typed '${typed}', expected '${expected}'). Aborting.${RESET}" >&2
        exit 1
    fi

    echo "${GREEN}Confirmed.${RESET}"
}

# confirm_phrase <phrase>
# Prompts the operator to type an exact phrase. Aborts on mismatch.
confirm_phrase() {
    local phrase="$1"
    printf "Type '%s' to proceed: " "$phrase"
    read -r typed
    if [ "$typed" != "$phrase" ]; then
        echo "${RED}Phrase mismatch. Aborting.${RESET}" >&2
        exit 1
    fi
}
