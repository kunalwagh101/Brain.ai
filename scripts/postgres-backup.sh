#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"

command -v pg_dump >/dev/null 2>&1 || {
  echo "pg_dump is required." >&2
  exit 69
}
command -v pg_restore >/dev/null 2>&1 || {
  echo "pg_restore is required." >&2
  exit 69
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "sha256sum is required." >&2
  exit 69
}

umask 077
mkdir -p "$(dirname "${BACKUP_FILE}")"

echo "Creating PostgreSQL custom-format backup for database '${PGDATABASE}'..."
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="${BACKUP_FILE}" \
  "${PGDATABASE}"

# Validate that the archive can at least be parsed before calling it a backup.
pg_restore --list "${BACKUP_FILE}" >/dev/null
sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"
chmod 600 "${BACKUP_FILE}" "${BACKUP_FILE}.sha256"

echo "Backup created and archive-validated: ${BACKUP_FILE}"
