#!/bin/bash
set -euo pipefail

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=postgres}"
: "${DB_NAME:=cmsdb}"
: "${CMS_ADMIN_USER:=admin}"
: "${CMS_ADMIN_PASSWORD:=admin}"

wait-for-it "${DB_HOST}:${DB_PORT}"

if ! psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c '\q' >/dev/null 2>&1; then
    echo "Creating database '${DB_NAME}'"
    createdb --host="$DB_HOST" --username="${DB_USER}" "${DB_NAME}"
fi

NUM_TABLES="$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
if [ "$NUM_TABLES" -eq 0 ]; then
    echo "Initializing database '${DB_NAME}'"
    cmsInitDB
fi

cmsAddAdmin "${CMS_ADMIN_USER}" -p "${CMS_ADMIN_PASSWORD}" >/dev/null 2>&1 || true
exec "$@"
