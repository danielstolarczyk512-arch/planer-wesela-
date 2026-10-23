#!/usr/bin/env bash
# Aktualizacja serwera Oracle do najnowszej wersji z GitHuba (docs/oracle-cloud.md).
#   sudo bash deploy/oracle/aktualizuj.sh
# Przed aktualizacją robi kopię bazy; migracje wykonuje kontener migrate.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "Uruchom przez sudo."; exit 1; }

/usr/local/bin/naszdzien-kopia
git -C "$REPO" pull --ff-only
docker run --rm -v "$REPO/frontend:/app" -w /app node:22-bookworm-slim \
  sh -c "npm ci --ignore-scripts --no-audit --no-fund && npm run build"
cd "$REPO/deploy"
docker compose -f compose.prod.yaml -f compose.oracle.yaml --env-file .env.prod up -d --build
docker image prune -f >/dev/null
echo "Zaktualizowano. Wersja: $(git -C "$REPO" log --oneline -1)"
