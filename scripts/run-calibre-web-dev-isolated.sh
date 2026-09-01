#!/usr/bin/env bash

set -euo pipefail

EMPTY_SOURCE_DIR="/home/feninf/calibre-web-dev-data/empty-source"
SOURCE_LIBRARY_DIR="/home/feninf/aubooks/library"
SOURCE_EXPORT_DIR="/home/feninf/aubooks/sync-export"
DEV_LIBRARY_DIR="/home/feninf/calibre-web-dev-data/library"

if [[ "$(id -u)" -ne 0 ]]; then
  printf 'Isolation launcher must run as root inside its user namespace.\n' >&2
  exit 1
fi
if [[ ! -d "$EMPTY_SOURCE_DIR" || ! -d "$SOURCE_LIBRARY_DIR" ||
      ! -d "$SOURCE_EXPORT_DIR" || ! -f "$DEV_LIBRARY_DIR/metadata.db" ]]; then
  printf 'Isolation launcher is missing a required path.\n' >&2
  exit 1
fi
shopt -s dotglob nullglob
empty_source_entries=("$EMPTY_SOURCE_DIR"/*)
shopt -u dotglob nullglob
if (( ${#empty_source_entries[@]} != 0 )); then
  printf 'Isolation launcher requires an empty source-mask directory.\n' >&2
  exit 1
fi

mount --bind "$EMPTY_SOURCE_DIR" "$SOURCE_LIBRARY_DIR"
mount -o remount,bind,ro "$SOURCE_LIBRARY_DIR"
mount --bind "$EMPTY_SOURCE_DIR" "$SOURCE_EXPORT_DIR"
mount -o remount,bind,ro "$SOURCE_EXPORT_DIR"
mount --bind "$DEV_LIBRARY_DIR" "$DEV_LIBRARY_DIR"
mount -o remount,bind,ro "$DEV_LIBRARY_DIR"

if [[ -e "$SOURCE_LIBRARY_DIR/metadata.db" || -e "$SOURCE_EXPORT_DIR/metadata.db" ||
      ! -r "$DEV_LIBRARY_DIR/metadata.db" || -w "$DEV_LIBRARY_DIR/metadata.db" ]]; then
  printf 'Isolation launcher failed to establish safe mounts.\n' >&2
  exit 1
fi

exec /usr/bin/setpriv --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all "$@"
