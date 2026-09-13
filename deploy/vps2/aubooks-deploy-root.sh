#!/usr/bin/env bash

set -Eeuo pipefail

readonly HELPER_NAME="deploy-calibre-web-release.sh"
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

helper="$bundle_dir/$HELPER_NAME"
[[ -f "$helper" ]] || fail 'helper is missing from bundle'
[[ ! -L "$helper" ]] || fail 'helper must not be a symlink'
[[ "$(stat -c '%a' "$helper")" =~ ^[0-7][0-7][0-5]$ ]] || fail 'helper has unsafe permissions'

exec "$helper" --bundle-dir "$bundle_dir" --commit-sha "$sha"
