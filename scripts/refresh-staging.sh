#!/usr/bin/env bash
# scripts/refresh-staging.sh
#
# Refreshes the staging database with a sanitized copy of production data.
# The staging DB will be DROPPED and re-created.
#
# Usage:
#   ./scripts/refresh-staging.sh
#
# Prerequisites:
#   - The db service must be running (via either compose stack)
#   - Production database "sipsense" must exist and have data
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

PROD_DB="sipsense"
STAGING_DB="sipsense_staging"
DB_USER="sipsense"
DUMP_FILE="/tmp/sipsense_prod_dump.sql"

# Use production compose to reach the db service
COMPOSE_PROD="-f docker-compose.yml -f docker-compose.production.yml"

echo "=== SipSense Staging Refresh ==="
echo ""
echo "This will DROP sipsense_staging and replace it with sanitized production data."
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ── Step 1: Verify production DB is reachable ────────────────────────
echo ""
echo "[1/5] Checking production database..."
docker compose ${COMPOSE_PROD} exec -T db pg_isready -U "${DB_USER}" -d "${PROD_DB}" \
    || { echo "ERROR: Production DB is not reachable. Is the db service running?"; exit 1; }

# ── Step 2: Dump production ──────────────────────────────────────────
echo "[2/5] Dumping production database..."
docker compose ${COMPOSE_PROD} exec -T db \
    pg_dump -U "${DB_USER}" --no-owner --no-acl "${PROD_DB}" > "${DUMP_FILE}"
echo "  Dump saved ($(du -h "${DUMP_FILE}" | cut -f1))"

# ── Step 3: Drop and recreate staging database ──────────────────────
echo "[3/5] Recreating staging database..."
docker compose ${COMPOSE_PROD} exec -T db psql -U "${DB_USER}" -d postgres <<-EOSQL
    -- Terminate any active connections to staging
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '${STAGING_DB}' AND pid <> pg_backend_pid();

    DROP DATABASE IF EXISTS ${STAGING_DB};
    CREATE DATABASE ${STAGING_DB} OWNER ${DB_USER};
EOSQL

# ── Step 4: Load dump into staging ───────────────────────────────────
echo "[4/5] Loading production data into staging..."
docker compose ${COMPOSE_PROD} exec -T db \
    psql -U "${DB_USER}" -d "${STAGING_DB}" < "${DUMP_FILE}"

# ── Step 5: Sanitize PII ────────────────────────────────────────────
echo "[5/5] Sanitizing staging data..."
docker compose ${COMPOSE_PROD} exec -T db \
    psql -U "${DB_USER}" -d "${STAGING_DB}" < "${SCRIPT_DIR}/sanitize-staging.sql"

# Clean up temp dump
rm -f "${DUMP_FILE}"

echo ""
echo "=== Staging refresh complete ==="
echo "  Database '${STAGING_DB}' now contains sanitized production data."
echo "  All users can log in with password: staging_test_password"
echo "  First user is: user_0001"
echo ""
echo "  Start staging with: ./scripts/start-staging.sh"
