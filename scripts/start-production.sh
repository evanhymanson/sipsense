#!/usr/bin/env bash
set -euo pipefail

echo "Starting SipSense in PRODUCTION mode..."
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
echo ""
echo "Production is running at http://localhost:80"
echo "Check health: curl http://localhost/api/"
