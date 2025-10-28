#!/bin/sh
set -eu

TEMPLATE=/etc/nginx/nginx.conf.template
OUT=/etc/nginx/nginx.conf
UPSTREAM_CONF=/etc/nginx/upstream.conf

: "${ACTIVE_POOL:=blue}"
: "${BLUE_HOST:=app_blue}"
: "${BLUE_PORT:=3000}"
: "${GREEN_HOST:=app_green}"
: "${GREEN_PORT:=3000}"

# Create upstream with primary + backup (primary first)
if [ "${ACTIVE_POOL}" = "green" ]; then
  PRIMARY_HOST=${GREEN_HOST}
  PRIMARY_PORT=${GREEN_PORT}
  BACKUP_HOST=${BLUE_HOST}
  BACKUP_PORT=${BLUE_PORT}
else
  PRIMARY_HOST=${BLUE_HOST}
  PRIMARY_PORT=${BLUE_PORT}
  BACKUP_HOST=${GREEN_HOST}
  BACKUP_PORT=${GREEN_PORT}
fi

cat > "${UPSTREAM_CONF}" <<EOF
upstream backend_pool {
    # primary - short max_fails and short fail_timeout to detect quickly
    server ${PRIMARY_HOST}:${PRIMARY_PORT} max_fails=1 fail_timeout=2s;
    # backup server
    server ${BACKUP_HOST}:${BACKUP_PORT} backup;
}
EOF

# Render final nginx.conf from template (template includes /etc/nginx/upstream.conf)
envsubst < "${TEMPLATE}" > "${OUT}"

# start nginx in foreground
nginx -g 'daemon off;'
