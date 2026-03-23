#!/usr/bin/env bash
set -euo pipefail

echo "Starting SipSense in STAGING mode..."
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build
echo ""
echo "Staging is running at http://localhost:8080"
echo "Check health: curl http://localhost:8080/api/"
