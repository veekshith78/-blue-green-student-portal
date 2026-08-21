#!/usr/bin/env sh
set -eu

# ACTIVE_COLOR is set as an env var on the Render service (blue or green).
# This picks which backend's public onrender.com URL nginx proxies to.
if [ "${ACTIVE_COLOR}" = "green" ]; then
    export ACTIVE_HOST="${GREEN_HOST}"
else
    export ACTIVE_HOST="${BLUE_HOST}"
fi

echo "==> Routing traffic to: ${ACTIVE_COLOR} (${ACTIVE_HOST})"

envsubst '${ACTIVE_HOST}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
