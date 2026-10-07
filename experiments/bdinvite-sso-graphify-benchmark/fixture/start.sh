#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting OIDC Test Container..."
docker compose up -d

echo "Waiting for OIDC Discovery Endpoint..."
RETRY=0
MAX_RETRIES=20
until curl -s -f http://localhost:8088/default/.well-known/openid-configuration > /dev/null 2>&1; do
  RETRY=$((RETRY+1))
  if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
    echo "ERROR: OIDC container failed to become ready in time."
    docker compose logs
    exit 1
  fi
  sleep 1
done

echo "✅ OIDC Test Container ready at http://localhost:8088/default"
