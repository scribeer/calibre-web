#!/usr/bin/env bash

set -euo pipefail

APP_DB="/home/feninf/calibre-web-dev-data/app.db"
DEV_LIBRARY_DIR="/home/feninf/calibre-web-dev-data/library"
SOURCE_DB="/home/feninf/aubooks/library/metadata.db"
DEV_METADATA_DB="$DEV_LIBRARY_DIR/metadata.db"

for command_name in realpath sqlite3 stat; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command is unavailable: %s\n' "$command_name" >&2
    exit 1
  fi
done

if [[ ! -f "$APP_DB" || ! -f "$DEV_METADATA_DB" || ! -f "$SOURCE_DB" ||
      -L "$APP_DB" || -L "$DEV_LIBRARY_DIR" || -L "$DEV_METADATA_DB" || -L "$SOURCE_DB" ]]; then
  printf 'DEV isolation check failed: a required database is missing.\n' >&2
  exit 1
fi

configured_library="$(sqlite3 -readonly "$APP_DB" 'PRAGMA query_only=ON; SELECT config_calibre_dir FROM settings LIMIT 1;')"
if [[ "$configured_library" != "$DEV_LIBRARY_DIR" ]]; then
  printf 'DEV isolation check failed: configured library is %s\n' "$configured_library" >&2
  exit 1
fi

source_real="$(realpath "$SOURCE_DB")"
snapshot_real="$(realpath "$DEV_METADATA_DB")"
if [[ "$source_real" == "$snapshot_real" || "$SOURCE_DB" -ef "$DEV_METADATA_DB" ]]; then
  printf 'DEV isolation check failed: snapshot resolves to the source database.\n' >&2
  exit 1
fi
if [[ "$(stat --format='%h' "$APP_DB")" != "1" || "$(stat --format='%h' "$DEV_METADATA_DB")" != "1" ]]; then
  printf 'DEV isolation check failed: a database has unexpected hard links.\n' >&2
  exit 1
fi

if [[ -w "$DEV_METADATA_DB" ]]; then
  printf 'DEV isolation check failed: snapshot is writable.\n' >&2
  exit 1
fi

safe_settings="$(sqlite3 -readonly "$APP_DB" 'PRAGMA query_only=ON; SELECT config_calibre_split || "|" || config_use_google_drive || "|" || config_uploading || "|" || schedule_metadata_backup || "|" || schedule_generate_book_covers || "|" || schedule_generate_series_covers FROM settings LIMIT 1;')"
if [[ "$safe_settings" != "0|0|0|0|0|0" ]]; then
  printf 'DEV isolation check failed: unsafe writer or external-storage setting: %s\n' "$safe_settings" >&2
  exit 1
fi

book_count="$(sqlite3 -readonly "$DEV_METADATA_DB" 'PRAGMA query_only=ON; SELECT COUNT(*) FROM books;')"
if [[ ! "$book_count" =~ ^[0-9]+$ || "$book_count" -eq 0 ]]; then
  printf 'DEV isolation check failed: snapshot book count is %s\n' "$book_count" >&2
  exit 1
fi

snapshot_integrity="$(sqlite3 -readonly "$DEV_METADATA_DB" 'PRAGMA query_only=ON; PRAGMA quick_check;')"
if [[ "$snapshot_integrity" != "ok" ]]; then
  printf 'DEV isolation check failed: snapshot quick check is %s\n' "$snapshot_integrity" >&2
  exit 1
fi

configured_uuid="$(sqlite3 -readonly "$APP_DB" 'PRAGMA query_only=ON; SELECT config_calibre_uuid FROM settings LIMIT 1;')"
snapshot_uuid="$(sqlite3 -readonly "$DEV_METADATA_DB" 'PRAGMA query_only=ON; SELECT uuid FROM library_id LIMIT 1;')"
if [[ -z "$snapshot_uuid" || "$configured_uuid" != "$snapshot_uuid" ]]; then
  printf 'DEV isolation check failed: configured and snapshot UUIDs differ.\n' >&2
  exit 1
fi

printf 'DEV library isolation verified: %s books in %s\n' "$book_count" "$snapshot_real"
