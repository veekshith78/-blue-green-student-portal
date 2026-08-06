#!/usr/bin/env bash
#
# Blue-Green traffic switcher.
#
# Usage:
#   ./scripts/switch.sh blue
#   ./scripts/switch.sh green
#
# What it does:
#   1. Health-checks the target color's container directly.
#   2. If healthy, rewrites nginx/active_upstream.conf to point at it.
#   3. Reloads nginx (zero-downtime, no restart).
#   4. If the health check fails, it aborts and leaves current traffic untouched.
#
set -euo pipefail

TARGET="${1:-}"
COMPOSE_PROJECT_NGINX_CONTAINER="nginx"
CONF_FILE="$(dirname "$0")/../nginx/active_upstream.conf"

if [[ "$TARGET" != "blue" && "$TARGET" != "green" ]]; then
  echo "Usage: $0 [blue|green]"
  exit 1
fi

TARGET_SERVICE="backend-${TARGET}"

echo "==> Health-checking ${TARGET_SERVICE}..."
if ! docker compose exec -T "${TARGET_SERVICE}" curl -sf http://localhost:5000/health > /dev/null; then
  echo "!! ${TARGET_SERVICE} failed its health check. Aborting switch. Traffic unchanged."
  exit 1
fi
echo "==> ${TARGET_SERVICE} is healthy."

cat > "${CONF_FILE}" <<EOF
# ACTIVE COLOR: ${TARGET}
upstream active_app {
    server ${TARGET_SERVICE}:5000;
}
EOF

echo "==> Reloading nginx..."
docker compose exec -T "${COMPOSE_PROJECT_NGINX_CONTAINER}" nginx -s reload

echo "==> Traffic switched to ${TARGET}. Zero downtime."
