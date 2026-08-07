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
#   2. If healthy, writes the new upstream config DIRECTLY INTO the running
#      nginx container's filesystem (via `docker compose exec`), rather than
#      writing to a host file path computed from this script's own location.
#      That matters because different runners (you, running this manually
#      from D:\blue-green-system; Jenkins, running it from its own separate
#      checkout folder) can have completely different "current directory"
#      contexts even when they're targeting the exact same running
#      containers. Writing straight into the container sidesteps that
#      entirely - it always lands in the one place that actually matters.
#   3. Reloads nginx (zero-downtime, no restart).
#   4. If the health check fails, it aborts and leaves current traffic untouched.
#
set -euo pipefail

TARGET="${1:-}"
NGINX_SERVICE="nginx"

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

echo "==> Writing new upstream config inside the nginx container..."
docker compose exec -T "${NGINX_SERVICE}" sh -c "cat > /etc/nginx/active_upstream.conf" <<EOF
# ACTIVE COLOR: ${TARGET}
upstream active_app {
    server ${TARGET_SERVICE}:5000;
}
EOF

echo "==> Reloading nginx..."
docker compose exec -T "${NGINX_SERVICE}" nginx -s reload

echo "==> Traffic switched to ${TARGET}. Zero downtime."
