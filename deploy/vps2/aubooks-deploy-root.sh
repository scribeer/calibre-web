#!/usr/bin/env bash

set -Eeuo pipefail

readonly HELPER="${HELPER:-/usr/local/sbin/aubooks-deploy-calibre-web}"
readonly STAGING_BASE="${STAGING_BASE:-/var/tmp}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || fail 'root wrapper accepts no command-line arguments'

sha=""
read -r sha || true
[[ -n "$sha" ]] || fail 'empty stdin'
[[ "${#sha}" -eq 40 ]] || fail 'expected exactly 40 hexadecimal characters'
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || fail 'SHA must be exactly 40 lowercase hexadecimal characters'

extra=""
IFS= read -r extra && fail 'unexpected trailing input after SHA' || true

bundle_dir="$STAGING_BASE/aubooks-calibre-web-$sha/deploy-bundle"
[[ -d "$bundle_dir" ]] || fail 'bundle directory does not exist'

exec "$HELPER" --bundle-dir "$bundle_dir" --commit-sha "$sha"
