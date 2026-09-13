#!/usr/bin/env bash

set -Eeuo pipefail

readonly HELPER="/usr/local/sbin/aubooks-deploy-calibre-web"
readonly STAGING_BASE="/var/tmp"

usage() {
  printf 'Usage: %s --bundle-dir PATH --commit-sha SHA\n' "$0" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

bundle_dir=""
commit_sha=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --bundle-dir)
      [[ "$#" -ge 2 ]] || fail '--bundle-dir requires a value'
      bundle_dir="$2"
      shift 2
      ;;
    --commit-sha)
      [[ "$#" -ge 2 ]] || fail '--commit-sha requires a value'
      commit_sha="$2"
      shift 2
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$bundle_dir" && -n "$commit_sha" ]] || { usage; fail '--bundle-dir and --commit-sha are required'; }
[[ "$commit_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'commit SHA must be exactly 40 lowercase hexadecimal characters'

expected_bundle="$STAGING_BASE/aubooks-calibre-web-$commit_sha/deploy-bundle"
[[ "$bundle_dir" == "$expected_bundle" ]] || fail 'bundle directory path mismatch'
[[ -d "$bundle_dir" ]] || fail 'bundle directory does not exist'

exec "$HELPER" --bundle-dir "$bundle_dir" --commit-sha "$commit_sha"
