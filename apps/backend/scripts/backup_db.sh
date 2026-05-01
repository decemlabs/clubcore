#!/usr/bin/env bash
# Phase A backup helper. Targets the compose-network postgres service so
# the host doesn't need pg_dump installed.
#
# Usage:
#   ./scripts/backup_db.sh                       # default ./backups/sportzal-<UTC>.sql.gz
#   ./scripts/backup_db.sh /tmp/my-dump.sql.gz   # custom path
#
# Requires: `docker compose up postgres` running (see ../docker-compose.yml).
set -euo pipefail

OUT="${1:-./backups/sportzal-$(date -u +%Y%m%dT%H%M%SZ).sql.gz}"
mkdir -p "$(dirname "$OUT")"

docker compose exec -T postgres pg_dump -U app -d sportzal | gzip > "$OUT"

SIZE=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")
echo "Wrote $OUT (${SIZE} bytes)"
