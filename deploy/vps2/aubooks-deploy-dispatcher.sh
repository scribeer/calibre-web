#!/usr/bin/env bash

set -Eeuo pipefail

readonly DEPLOY_USER="${AUBOOKS_DEPLOY_USER:-aubooks-deploy}"
readonly ROOT_WRAPPER="/usr/local/sbin/aubooks-deploy-root"
readonly STAGING_BASE="${STAGING_BASE:-/var/tmp}"

usage() {
  printf 'Usage: %s\n' "$0" >&2
  printf 'Forced-command dispatcher for AU-Books production deploy.\n' >&2
  printf 'SSH_ORIGINAL_COMMAND must be exactly:\n' >&2
  printf '  upload <40hex-sha>\n' >&2
  printf '  deploy <40hex-sha>\n' >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

command="${SSH_ORIGINAL_COMMAND:-}"

[[ -n "$command" ]] || fail 'SSH_ORIGINAL_COMMAND is empty'
[[ "$#" -eq 0 ]] || fail 'no positional arguments allowed'

set -- $command

[[ "$#" -ge 2 ]] || fail 'command requires exactly: <verb> <40hex-sha>'
[[ "$#" -eq 2 ]] || fail 'too many arguments'

verb="$1"
sha="$2"

[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || fail 'SHA must be exactly 40 lowercase hexadecimal characters'

staging="$STAGING_BASE/aubooks-calibre-web-$sha"
bundle_dir="$staging/deploy-bundle"

case "$verb" in
  upload)
    [[ ! -e "$bundle_dir" ]] || fail 'bundle directory already exists; refusing partial overwrite'
    install -d -m 0700 "$staging"
    install -d -m 0700 "$bundle_dir"
    tar -x -C "$bundle_dir" \
      --no-same-owner --no-same-permissions \
      --no-recursion \
      --wildcards 'calibreweb-*.whl' 'SHA256SUMS' 'artifact-manifest.json' 'deploy-request.json'
    python3 - "$bundle_dir" <<'PY'
import os
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
for entry in bundle.iterdir():
    if entry.is_symlink():
        raise SystemExit("symlink in bundle: {}".format(entry.name))
    if not entry.is_file():
        raise SystemExit("unexpected entry in bundle: {}".format(entry.name))
    if entry.name.startswith("/"):
        raise SystemExit("absolute path in bundle: {}".format(entry.name))
    resolved = entry.resolve()
    if not str(resolved).startswith(str(bundle.resolve())):
        raise SystemExit("path traversal in bundle: {}".format(entry.name))
PY
    if [[ "$(id -u)" == "0" ]]; then
      chown -R "$DEPLOY_USER:$DEPLOY_USER" "$staging"
    fi
    chmod 0700 "$staging" "$bundle_dir"
    for f in "$bundle_dir"/*; do
      [[ -f "$f" && ! -L "$f" ]] || fail "unexpected file in bundle: $(basename "$f")"
      chmod 0644 "$f"
    done
    printf 'upload %s OK\n' "$sha"
    ;;
  deploy)
    [[ -d "$bundle_dir" ]] || fail 'bundle directory does not exist; upload first'
    [[ "$(id -u)" == "0" ]] || fail 'dispatcher must run as root for deploy'
    owner="$(stat -c '%U' "$bundle_dir")"
    [[ "$owner" == "$DEPLOY_USER" ]] || fail 'bundle directory has unexpected owner'
    exec "$ROOT_WRAPPER" --bundle-dir "$bundle_dir" --commit-sha "$sha"
    ;;
  *)
    fail "unknown verb: $verb"
    ;;
esac
