#!/usr/bin/env bash

set -Eeuo pipefail

readonly DEPLOY_USER="${AUBOOKS_DEPLOY_USER:-aubooks-deploy}"
readonly ROOT_WRAPPER="/usr/local/sbin/aubooks-deploy-root"
readonly STAGING_BASE="${STAGING_BASE:-/var/tmp}"
readonly MAX_ARCHIVE_BYTES=$((512 * 1024 * 1024))
readonly MAX_WHEEL_BYTES=$((256 * 1024 * 1024))
readonly MAX_METADATA_BYTES=$((256 * 1024))
readonly MAX_HELPER_BYTES=$((256 * 1024))

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
    tmp_archive="$(mktemp "$staging/archive.XXXXXX")"
    cleanup() { rm -rf "$staging"; }
    trap cleanup ERR
    cat > "$tmp_archive"
    archive_size="$(stat -c '%s' "$tmp_archive")"
    (( archive_size <= MAX_ARCHIVE_BYTES )) || fail "archive exceeds maximum size: ${archive_size} bytes"
    (( archive_size > 0 )) || fail 'archive is empty'
    python3 - "$tmp_archive" "$bundle_dir" "$DEPLOY_USER" "$MAX_WHEEL_BYTES" "$MAX_METADATA_BYTES" "$MAX_HELPER_BYTES" <<'PY'
import os
import sys
import tarfile
from pathlib import Path

archive_path = Path(sys.argv[1])
bundle_dir = Path(sys.argv[2])
deploy_user = sys.argv[3]
max_wheel = int(sys.argv[4])
max_metadata = int(sys.argv[5])
max_helper = int(sys.argv[6])

ALLOWED_NAMES = {"SHA256SUMS", "artifact-manifest.json", "deploy-request.json", "deploy-calibre-web-release.sh", "sync-audio-db.sh", "tts_processor.py"}
ALLOWED_EXTS = {".whl"}

def validate_member(member):
    if member.name != member.name.split("/")[-1]:
        raise SystemExit("nested path rejected: {}".format(member.name))
    if member.name.startswith("/"):
        raise SystemExit("absolute path rejected: {}".format(member.name))
    if ".." in member.name.split("/"):
        raise SystemExit("path traversal rejected: {}".format(member.name))
    if member.issym() or member.islnk():
        raise SystemExit("symlink/hardlink rejected: {}".format(member.name))
    if member.isdev():
        raise SystemExit("device file rejected: {}".format(member.name))
    if member.isdir():
        raise SystemExit("directory rejected: {}".format(member.name))
    if not member.isfile():
        raise SystemExit("non-regular file rejected: {}".format(member.name))

with tarfile.open(archive_path, "r:*") as tar:
    members = tar.getmembers()
    if len(members) != 7:
        raise SystemExit("expected exactly 7 archive members, found {}".format(len(members)))

    seen = set()
    for member in members:
        validate_member(member)
        if member.name in seen:
            raise SystemExit("duplicate filename rejected: {}".format(member.name))
        seen.add(member.name)

        is_wheel = member.name.startswith("calibreweb-") and member.name.endswith(".whl")
        is_helper = member.name == "deploy-calibre-web-release.sh"
        is_metadata = member.name in ALLOWED_NAMES

        if not (is_wheel or is_helper or is_metadata):
            raise SystemExit("unexpected file rejected: {}".format(member.name))

        if is_wheel and len(seen - ALLOWED_NAMES) > 1:
            raise SystemExit("expected exactly one wheel, found extra: {}".format(member.name))

        if is_wheel:
            limit = max_wheel
        elif is_helper:
            limit = max_helper
        else:
            limit = max_metadata
        if member.size > limit:
            raise SystemExit("file exceeds size limit: {} ({} bytes)".format(member.name, member.size))

    if len(seen - ALLOWED_NAMES) != 1:
        raise SystemExit("expected exactly one wheel file")

    for member in members:
        data = tar.extractfile(member)
        if data is None:
            raise SystemExit("cannot read member: {}".format(member.name))
        content = data.read()
        if len(content) != member.size:
            raise SystemExit("size mismatch for {}: expected {} got {}".format(
                member.name, member.size, len(content)))
        target = bundle_dir / member.name
        target.write_bytes(content)
        if member.name == "deploy-calibre-web-release.sh":
            os.chmod(target, 0o755)
        else:
            os.chmod(target, 0o644)

for entry in bundle_dir.iterdir():
    if entry.is_symlink():
        raise SystemExit("symlink in bundle: {}".format(entry.name))
    if not entry.is_file():
        raise SystemExit("unexpected entry in bundle: {}".format(entry.name))

if os.getuid() == 0:
    for entry in bundle_dir.iterdir():
        os.chown(entry, deploy_user, deploy_user)
PY
    rm -f "$tmp_archive"
    trap - ERR
    chmod 0700 "$staging" "$bundle_dir"
    printf 'upload %s OK\n' "$sha"
    ;;
  deploy)
    [[ -d "$bundle_dir" ]] || fail 'bundle directory does not exist; upload first'
    owner="$(stat -c '%U' "$bundle_dir")"
    [[ "$owner" == "$DEPLOY_USER" ]] || fail 'bundle directory has unexpected owner'
    printf '%s\n' "$sha" | sudo -n "$ROOT_WRAPPER"
    ;;
  *)
    fail "unknown verb: $verb"
    ;;
esac
