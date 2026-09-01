#!/usr/bin/env bash

set -euo pipefail

SOURCE_DB="${SOURCE_DB:-/home/feninf/aubooks/library/metadata.db}"
DEV_LIBRARY_DIR="${DEV_LIBRARY_DIR:-/home/feninf/calibre-web-dev-data/library}"
DEST_DB="$DEV_LIBRARY_DIR/metadata.db"

umask 027

for command_name in flock mktemp realpath sqlite3 stat; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command is unavailable: %s\n' "$command_name" >&2
    exit 1
  fi
done

if [[ ! -f "$SOURCE_DB" || ! -r "$SOURCE_DB" || -L "$SOURCE_DB" ]]; then
  printf 'Source metadata database is not readable: %s\n' "$SOURCE_DB" >&2
  exit 1
fi

mkdir -p "$DEV_LIBRARY_DIR"
if [[ -L "$DEV_LIBRARY_DIR" ]]; then
  printf 'Refusing to use a symlinked DEV library directory: %s\n' "$DEV_LIBRARY_DIR" >&2
  exit 1
fi

source_real="$(realpath "$SOURCE_DB")"
destination_real="$(realpath -m "$DEST_DB")"
if [[ "$source_real" == "$destination_real" || ( -e "$DEST_DB" && "$SOURCE_DB" -ef "$DEST_DB" ) ]]; then
  printf 'Refusing to replace the source database with itself: %s\n' "$source_real" >&2
  exit 1
fi
if [[ -L "$DEST_DB" ]]; then
  printf 'Refusing to replace a symlinked DEV metadata database: %s\n' "$DEST_DB" >&2
  exit 1
fi
if [[ -e "$DEST_DB" && ! -f "$DEST_DB" ]]; then
  printf 'Refusing to replace a non-regular DEV metadata path: %s\n' "$DEST_DB" >&2
  exit 1
fi
if [[ -e "$DEST_DB-wal" || -e "$DEST_DB-shm" || -e "$DEST_DB-journal" ]]; then
  printf 'Refusing to replace DEV metadata while SQLite sidecar files exist.\n' >&2
  exit 1
fi

exec 9<"$DEV_LIBRARY_DIR"
if ! flock -n 9; then
  printf 'Another DEV snapshot update is already running.\n' >&2
  exit 1
fi

temp_db="$(mktemp "$DEV_LIBRARY_DIR/.metadata.db.XXXXXX")"
cleanup() {
  rm -f "$temp_db"
}
trap cleanup EXIT INT TERM
if [[ ! -f "$temp_db" || -L "$temp_db" || "$(stat --format='%h' "$temp_db")" != "1" ]]; then
  printf 'Temporary snapshot path is not a private regular file.\n' >&2
  exit 1
fi

escaped_temp_db="${temp_db//\'/\'\'}"
sqlite3 -readonly "$SOURCE_DB" ".backup '$escaped_temp_db'"

snapshot_integrity="$(sqlite3 -readonly "$temp_db" 'PRAGMA query_only=ON; PRAGMA integrity_check;')"
if [[ "$snapshot_integrity" != "ok" ]]; then
  printf 'Snapshot integrity check failed: %s\n' "$snapshot_integrity" >&2
  exit 1
fi

snapshot_count="$(sqlite3 -readonly "$temp_db" 'PRAGMA query_only=ON; SELECT COUNT(*) FROM books;')"
snapshot_uuid="$(sqlite3 -readonly "$temp_db" 'PRAGMA query_only=ON; SELECT uuid FROM library_id LIMIT 1;')"

if [[ ! "$snapshot_count" =~ ^[0-9]+$ || "$snapshot_count" -eq 0 ]]; then
  printf 'Snapshot has an invalid book count: %s\n' "$snapshot_count" >&2
  exit 1
fi
if [[ -z "$snapshot_uuid" ]]; then
  printf 'Snapshot library UUID is empty.\n' >&2
  exit 1
fi

chmod 0444 "$temp_db"
mv -f "$temp_db" "$DEST_DB"
trap - EXIT INT TERM

printf 'DEV metadata snapshot updated.\n'
printf 'Source: %s\n' "$source_real"
printf 'Destination: %s\n' "$DEST_DB"
printf 'Books: %s\n' "$snapshot_count"
printf 'Library UUID: %s\n' "$snapshot_uuid"
printf 'Restart calibre-web-dev.service before runtime verification.\n'
