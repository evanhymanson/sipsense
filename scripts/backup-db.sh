#!/usr/bin/env bash
# Usage: ./scripts/backup-db.sh [staging|production]
# Creates a compressed PostgreSQL backup in the backups/ directory.
set -euo pipefail

ENV="${1:-production}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"
BACKUP_FILE="${BACKUP_DIR}/sipsense_${ENV}_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

if [ "$ENV" = "staging" ]; then
    DB_NAME="sipsense_staging"
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.staging.yml"
else
    DB_NAME="sipsense"
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.production.yml"
fi

echo "Backing up ${DB_NAME} (${ENV})..."
docker compose ${COMPOSE_FILES} exec -T db \
    pg_dump -U sipsense "${DB_NAME}" | gzip > "${BACKUP_FILE}"

SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup saved to ${BACKUP_FILE} (${SIZE})"
