#!/usr/bin/env bash
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${RESTORE_FILE:?RESTORE_FILE is required}"

required_confirmation="I_UNDERSTAND_THIS_REPLACES_DATABASE"
if [[ "${BRAIN_RESTORE_CONFIRM:-}" != "${required_confirmation}" ]]; then
  echo "Restore refused. Set BRAIN_RESTORE_CONFIRM=${required_confirmation}." >&2
  exit 64
fi

command -v pg_restore >/dev/null 2>&1 || {
  echo "pg_restore is required." >&2
  exit 69
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "sha256sum is required." >&2
  exit 69
}

if [[ ! -r "${RESTORE_FILE}" ]]; then
  echo "Restore archive is not readable: ${RESTORE_FILE}" >&2
  exit 66
fi

checksum_file="${RESTORE_FILE}.sha256"
if [[ -f "${checksum_file}" ]]; then
  (cd "$(dirname "${RESTORE_FILE}")" && sha256sum --check "$(basename "${checksum_file}")")
else
  echo "Restore refused because checksum file is missing: ${checksum_file}" >&2
  exit 65
fi

# Parse the archive before making destructive changes.
pg_restore --list "${RESTORE_FILE}" >/dev/null

echo "Restoring database '${PGDATABASE}' from verified archive..."
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --exit-on-error \
  --dbname="${PGDATABASE}" \
  "${RESTORE_FILE}"

echo "Restore completed: ${RESTORE_FILE}"
