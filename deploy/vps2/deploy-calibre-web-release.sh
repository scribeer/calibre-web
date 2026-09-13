#!/usr/bin/env bash

set -Eeuo pipefail

readonly DEFAULT_ROOT="/opt/calibre-web"
readonly SERVICE_NAME="calibre-web.service"
readonly MIN_FREE_KB="${AUBOOKS_MIN_FREE_KB:-1048576}"
readonly HEALTH_STARTUP_TIMEOUT="${AUBOOKS_HEALTH_STARTUP_TIMEOUT:-30}"
readonly HEALTH_RETRY_INTERVAL="${AUBOOKS_HEALTH_RETRY_INTERVAL:-1}"

BUNDLE_DIR=""
COMMIT_SHA=""
DRY_RUN=0
DEPLOY_ROOT="${AUBOOKS_DEPLOY_ROOT:-$DEFAULT_ROOT}"
DEPLOY_STARTED=0
SWITCHED=0
DB_CHANGED=0
SERVICE_STOPPED=0
PREVIOUS_RELEASE=""
APP_DB_BACKUP=""
APP_DB_UID=""
APP_DB_GID=""
APP_DB_MODE=""
WHEEL_FILENAME=""
WHEEL_SHA256=""
PUBLIC_URL=""
RELEASE_DIR=""
SERVICE_USER=""

usage() {
  printf 'Usage: %s --bundle-dir PATH --commit-sha SHA [--dry-run]\n' "$0" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

plan() {
  printf 'DRY_RUN: %s\n' "$*"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --bundle-dir)
      [[ "$#" -ge 2 ]] || fail '--bundle-dir requires a value'
      BUNDLE_DIR="$2"
      shift 2
      ;;
    --commit-sha)
      [[ "$#" -ge 2 ]] || fail '--commit-sha requires a value'
      COMMIT_SHA="${2,,}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      usage
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$BUNDLE_DIR" && -n "$COMMIT_SHA" ]] || {
  usage
  fail '--bundle-dir and --commit-sha are required'
}
[[ "$COMMIT_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'commit SHA must be exactly 40 lowercase hexadecimal characters'
[[ -d "$BUNDLE_DIR" ]] || fail "bundle directory does not exist: $BUNDLE_DIR"
[[ ! -L "$BUNDLE_DIR" ]] || fail 'bundle directory must not be a symlink'
[[ "$MIN_FREE_KB" =~ ^[0-9]+$ ]] || fail 'AUBOOKS_MIN_FREE_KB must be a non-negative integer'
[[ "$HEALTH_STARTUP_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || fail 'AUBOOKS_HEALTH_STARTUP_TIMEOUT must be a positive integer'
[[ "$HEALTH_RETRY_INTERVAL" =~ ^[1-9][0-9]*$ ]] || fail 'AUBOOKS_HEALTH_RETRY_INTERVAL must be a positive integer'

for command_name in chmod chown curl df flock grep id install journalctl python3 readlink runuser sha256sum sleep ss stat systemctl; do
  command -v "$command_name" >/dev/null 2>&1 || fail "required command is unavailable: $command_name"
done
[[ "$(id -u)" == "0" ]] || fail 'helper must run as root or through sudo'

readonly CONFIG_DIR="$DEPLOY_ROOT/config"
readonly LIBRARY_DIR="$DEPLOY_ROOT/library"
readonly RELEASES_DIR="$DEPLOY_ROOT/releases"
readonly BACKUPS_DIR="$DEPLOY_ROOT/backups"
readonly CURRENT_LINK="$DEPLOY_ROOT/current"
readonly APP_DB="$CONFIG_DIR/app.db"
readonly GDRIVE_DB="$CONFIG_DIR/gdrive.db"
readonly METADATA_DB="$LIBRARY_DIR/metadata.db"

validate_bundle() {
  local manifest="$BUNDLE_DIR/artifact-manifest.json"
  local request="$BUNDLE_DIR/deploy-request.json"
  local sums="$BUNDLE_DIR/SHA256SUMS"
  local manifest_output

  [[ -f "$manifest" && ! -L "$manifest" ]] || fail 'artifact-manifest.json is missing or unsafe'
  [[ -f "$request" && ! -L "$request" ]] || fail 'deploy-request.json is missing or unsafe'
  [[ -f "$sums" && ! -L "$sums" ]] || fail 'SHA256SUMS is missing or unsafe'

  manifest_output="$(python3 - "$manifest" "$request" "$COMMIT_SHA" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as file_handle:
    manifest = json.load(file_handle)
with open(sys.argv[2], encoding="utf-8") as file_handle:
    request = json.load(file_handle)

commit_sha = sys.argv[3]
if manifest.get("commit_sha") != commit_sha:
    raise SystemExit("manifest commit SHA does not match --commit-sha")
if manifest.get("repository") != "scribeer/calibre-web":
    raise SystemExit("manifest repository is not canonical")
if manifest.get("ref") != "refs/heads/aubooks":
    raise SystemExit("manifest ref is not aubooks")
wheel_filename = manifest.get("wheel_filename", "")
wheel_sha256 = manifest.get("wheel_sha256", "")
if not re.fullmatch(r"calibreweb-[A-Za-z0-9_.+!-]+\.whl", wheel_filename):
    raise SystemExit("manifest wheel filename is invalid")
if not re.fullmatch(r"[0-9a-f]{64}", wheel_sha256):
    raise SystemExit("manifest wheel SHA-256 is invalid")
helper_filename = manifest.get("helper_filename", "")
helper_sha256 = manifest.get("helper_sha256", "")
if helper_filename != "deploy-calibre-web-release.sh":
    raise SystemExit("manifest helper filename is invalid")
if not re.fullmatch(r"[0-9a-f]{64}", helper_sha256):
    raise SystemExit("manifest helper SHA-256 is invalid")
if request.get("commit_sha") != commit_sha:
    raise SystemExit("deploy request commit SHA mismatch")
if request.get("wheel_filename") != wheel_filename:
    raise SystemExit("deploy request wheel filename mismatch")
if request.get("wheel_sha256") != wheel_sha256:
    raise SystemExit("deploy request wheel SHA-256 mismatch")
if request.get("repository") != manifest.get("repository"):
    raise SystemExit("deploy request repository mismatch")
if str(request.get("github_run_id")) != str(manifest.get("run_id")):
    raise SystemExit("deploy request CI run mismatch")
if str(request.get("github_run_attempt")) != str(manifest.get("run_attempt")):
    raise SystemExit("deploy request CI run attempt mismatch")
public_url = request.get("public_url") or "https://au-books.net/"
if not re.fullmatch(r"https://[^\s/]+(?:/.*)?", public_url):
    raise SystemExit("deploy request public URL is invalid")
print(wheel_filename)
print(wheel_sha256)
print(public_url)
print(helper_filename)
print(helper_sha256)
PY
  )" || fail 'bundle manifest validation failed'
  mapfile -t manifest_values <<< "$manifest_output"
  [[ "${#manifest_values[@]}" -eq 5 ]] || fail 'bundle manifest output is incomplete'
  WHEEL_FILENAME="${manifest_values[0]}"
  WHEEL_SHA256="${manifest_values[1]}"
  PUBLIC_URL="${manifest_values[2]}"
  HELPER_FILENAME="${manifest_values[3]}"
  HELPER_SHA256="${manifest_values[4]}"

  [[ -f "$BUNDLE_DIR/$WHEEL_FILENAME" && ! -L "$BUNDLE_DIR/$WHEEL_FILENAME" ]] || fail 'manifest wheel is missing or unsafe'
  [[ -f "$BUNDLE_DIR/$HELPER_FILENAME" && ! -L "$BUNDLE_DIR/$HELPER_FILENAME" ]] || fail 'manifest helper is missing or unsafe'
  python3 - "$BUNDLE_DIR/$WHEEL_FILENAME" "$BUNDLE_DIR/$HELPER_FILENAME" "$BUNDLE_DIR/SHA256SUMS" "$WHEEL_FILENAME" "$WHEEL_SHA256" "$HELPER_FILENAME" "$HELPER_SHA256" <<'PY'
import hashlib
import pathlib
import sys

wheel = pathlib.Path(sys.argv[1])
helper = pathlib.Path(sys.argv[2])
sums = pathlib.Path(sys.argv[3]).read_text(encoding="ascii").splitlines()
expected_wheel_name = sys.argv[4]
expected_wheel_sha = sys.argv[5]
expected_helper_name = sys.argv[6]
expected_helper_sha = sys.argv[7]

allowed_names = {expected_wheel_name, expected_helper_name}
entries = {}
for line in sums:
    parts = line.split()
    if len(parts) != 2:
        raise SystemExit("SHA256SUMS line has invalid format: {}".format(line))
    digest, name = parts
    name = name.lstrip("*")
    if name in entries:
        raise SystemExit("SHA256SUMS contains duplicate entry: {}".format(name))
    if name not in allowed_names:
        raise SystemExit("SHA256SUMS contains unexpected entry: {}".format(name))
    if not __import__("re").fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit("SHA256SUMS has malformed checksum for {}".format(name))
    entries[name] = digest

if len(entries) != 2:
    raise SystemExit("SHA256SUMS must contain exactly 2 entries, found {}".format(len(entries)))
if entries[expected_wheel_name] != expected_wheel_sha:
    raise SystemExit("SHA256SUMS wheel checksum does not match manifest")
if entries[expected_helper_name] != expected_helper_sha:
    raise SystemExit("SHA256SUMS helper checksum does not match manifest")

wheel_digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
if wheel_digest != expected_wheel_sha:
    raise SystemExit("wheel file checksum mismatch")
helper_digest = hashlib.sha256(helper.read_bytes()).hexdigest()
if helper_digest != expected_helper_sha:
    raise SystemExit("helper file checksum mismatch")
PY
  (
    cd "$BUNDLE_DIR"
    sha256sum -c SHA256SUMS >/dev/null
  ) || fail 'bundle checksum verification failed'
}

validate_app_database() {
  python3 - "$APP_DB" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect("file:{}?mode=ro".format(sys.argv[1]), uri=True)
try:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise SystemExit("app.db integrity check failed: {}".format(result))
    columns = {row[1] for row in connection.execute("PRAGMA table_info(settings)")}
    if "config_theme" not in columns:
        raise SystemExit("app.db settings.config_theme is missing")
    rows = connection.execute("SELECT config_theme FROM settings").fetchall()
    if len(rows) != 1:
        raise SystemExit("app.db must contain exactly one settings row")
finally:
    connection.close()
PY
}

read_config_theme() {
  python3 - "$APP_DB" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect("file:{}?mode=ro".format(sys.argv[1]), uri=True)
try:
    print(connection.execute("SELECT config_theme FROM settings").fetchone()[0])
finally:
    connection.close()
PY
}

validate_platform() {
  local path
  local available_kb

  for path in "$APP_DB" "$GDRIVE_DB" "$METADATA_DB"; do
    [[ -f "$path" && ! -L "$path" ]] || fail "required database is missing or unsafe: $path"
  done
  systemctl cat "$SERVICE_NAME" >/dev/null 2>&1 || fail "$SERVICE_NAME is not installed"
  SERVICE_USER="$(systemctl show --property=User --value "$SERVICE_NAME")"
  [[ "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]*$ && "$SERVICE_USER" != "root" ]] || fail "$SERVICE_NAME must declare a non-root User"
  id "$SERVICE_USER" >/dev/null 2>&1 || fail "service user does not exist: $SERVICE_USER"

  for path in "$DEPLOY_ROOT" "$CONFIG_DIR" "$LIBRARY_DIR"; do
    [[ -d "$path" && ! -L "$path" ]] || fail "required release-layout directory is missing or unsafe: $path"
  done
  if [[ ! -L "$CURRENT_LINK" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      printf 'INITIAL_MIGRATION_REQUIRED: current release symlink is absent; no migration was attempted\n'
      exit 0
    fi
    fail 'INITIAL_MIGRATION_REQUIRED: current release symlink is absent; run an explicit initial migration first'
  fi
  for path in "$RELEASES_DIR" "$BACKUPS_DIR"; do
    [[ -d "$path" && ! -L "$path" ]] || fail "required release-layout directory is missing or unsafe: $path"
  done
  PREVIOUS_RELEASE="$(readlink -f "$CURRENT_LINK")"
  [[ -d "$PREVIOUS_RELEASE" ]] || fail 'current release target does not exist'
  [[ "$PREVIOUS_RELEASE" == "$RELEASES_DIR/"* ]] || fail 'current release target is outside releases/'

  available_kb="$(df -Pk "$DEPLOY_ROOT" | python3 -c 'import sys; lines=sys.stdin.read().splitlines(); print(lines[-1].split()[3] if len(lines) >= 2 else "")')"
  [[ "$available_kb" =~ ^[0-9]+$ ]] || fail 'could not determine free disk space'
  (( available_kb >= MIN_FREE_KB )) || fail "insufficient free space: ${available_kb}KB available, ${MIN_FREE_KB}KB required"
  validate_app_database
  APP_DB_UID="$(stat -c '%u' "$APP_DB")"
  APP_DB_GID="$(stat -c '%g' "$APP_DB")"
  APP_DB_MODE="$(stat -c '%a' "$APP_DB")"
}

acquire_lock() {
  exec 9<"$DEPLOY_ROOT"
  flock -n 9 || fail 'another Calibre-Web deployment is already running'
}

restore_app_db_metadata() {
  [[ -n "$APP_DB_UID" && -n "$APP_DB_GID" && -n "$APP_DB_MODE" ]] || return 0
  chown "$APP_DB_UID:$APP_DB_GID" "$APP_DB"
  chmod "$APP_DB_MODE" "$APP_DB"
}

backup_databases() {
  local backup_dir="$BACKUPS_DIR/${COMMIT_SHA}-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -m 0700 "$backup_dir"
  APP_DB_BACKUP="$backup_dir/app.db"
  python3 - "$APP_DB" "$APP_DB_BACKUP" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
destination = sqlite3.connect(sys.argv[2])
try:
    source.backup(destination)
finally:
    destination.close()
    source.close()
PY
  cp --preserve=mode,timestamps "$GDRIVE_DB" "$backup_dir/gdrive.db"
  printf 'Database backup created: %s\n' "$backup_dir"
}

create_candidate_release() {
  local venv="$RELEASE_DIR/venv"
  local release_wheel="$RELEASE_DIR/$WHEEL_FILENAME"
  install -d -m 0755 -o root -g root "$RELEASE_DIR"
  install -d -m 0755 -o "$SERVICE_USER" "$venv"
  install -m 0444 -o root -g root "$BUNDLE_DIR/$WHEEL_FILENAME" "$release_wheel"
  printf '%s  %s\n' "$WHEEL_SHA256" "$WHEEL_FILENAME" > "$RELEASE_DIR/SHA256SUMS"
  (
    cd "$RELEASE_DIR"
    sha256sum -c SHA256SUMS >/dev/null
  )
  runuser -u "$SERVICE_USER" -- python3 -m venv "$venv"
  runuser -u "$SERVICE_USER" -- "$venv/bin/python" -m pip install "$release_wheel"
  runuser -u "$SERVICE_USER" -- "$venv/bin/python" -m pip check
  (
    cd /
    runuser -u "$SERVICE_USER" -- "$venv/bin/cps" --help >/dev/null
    runuser -u "$SERVICE_USER" -- "$venv/bin/python" - <<'PY'
from calibreweb.cps import themes, ub

theme = themes.get_theme(3)
assert theme["id"] == 3 and theme["identifier"] == "aubooks"
assert ub.Invite and callable(ub.create_invite)
PY
  )
  printf 'Candidate release ready: %s\n' "$RELEASE_DIR"
}

set_aubooks_theme_if_needed() {
  local current_theme
  current_theme="$(read_config_theme)"
  if [[ "$current_theme" == "3" ]]; then
    printf 'CONFIG_THEME_ALREADY_3\n'
    return
  fi
  [[ -n "$APP_DB_BACKUP" && -f "$APP_DB_BACKUP" ]] || fail 'app.db backup is required before changing config_theme'
  runuser -u "$SERVICE_USER" -- "$RELEASE_DIR/venv/bin/python" - <<'PY'
from calibreweb.cps import themes

theme = themes.get_theme(3)
assert theme["id"] == 3 and theme["identifier"] == "aubooks"
PY
  systemctl stop "$SERVICE_NAME"
  SERVICE_STOPPED=1
  DB_CHANGED=1
  runuser -u "$SERVICE_USER" -- python3 - "$APP_DB" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
try:
    connection.execute("BEGIN IMMEDIATE")
    cursor = connection.execute("UPDATE settings SET config_theme = 3 WHERE config_theme != 3")
    if cursor.rowcount != 1:
        raise RuntimeError("expected exactly one settings row to change")
    connection.commit()
except Exception:
    connection.rollback()
    raise
finally:
    connection.close()
PY
  restore_app_db_metadata
  printf 'config_theme changed transactionally to 3\n'
}

switch_current_release() {
  local next_link="$DEPLOY_ROOT/.current.$COMMIT_SHA"
  ln -s "$RELEASE_DIR" "$next_link"
  mv -Tf "$next_link" "$CURRENT_LINK"
  SWITCHED=1
}

restart_service() {
  systemctl restart "$SERVICE_NAME"
}

health_diagnostics() {
  local reason="$1"
  local service_state="$2"
  local port_state="$3"
  local http_result="$4"
  local journal_output

  printf 'ERROR: health check %s\n' "$reason" >&2
  printf 'HEALTH_SERVICE_STATE=%s\n' "${service_state:-unknown}" >&2
  printf 'HEALTH_PORT_STATE=%s\n' "$port_state" >&2
  printf 'HEALTH_LAST_HTTP_RESULT=%s\n' "$http_result" >&2
  journal_output="$(journalctl -u "$SERVICE_NAME" --since "@$DEPLOY_STARTED_AT" --no-pager -n 100 2>&1)" || true
  printf 'HEALTH_JOURNAL_BEGIN\n%s\nHEALTH_JOURNAL_END\n' "$journal_output" >&2
}

health_check() {
  local deadline=$((SECONDS + HEALTH_STARTUP_TIMEOUT))
  local service_state="unknown"
  local port_state="not-listening"
  local last_http_result="not-attempted"
  local local_http_output=""
  local local_ok=0
  local public_ok=0
  local login_ok=0
  local journal_output

  while (( SECONDS < deadline )); do
    service_state="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)"
    case "$service_state" in
      failed|inactive|deactivating)
        health_diagnostics 'aborted because service is not starting' "$service_state" "$port_state" "$last_http_result"
        return 1
        ;;
    esac

    port_state="not-listening"
    if ss -ltn | python3 -c 'import sys; raise SystemExit(0 if any(len(fields := line.split()) > 3 and fields[3] == "127.0.0.1:8083" for line in sys.stdin) else 1)'; then
      port_state="listening"
      if local_http_output="$(curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:8083/" 2>&1)"; then
        local_ok=1
        last_http_result="success"
        break
      else
        last_http_result="failure: ${local_http_output:-no response}"
      fi
    fi
    sleep "$HEALTH_RETRY_INTERVAL"
  done

  if [[ "$local_ok" -ne 1 ]]; then
    health_diagnostics "timed out after ${HEALTH_STARTUP_TIMEOUT}s" "$service_state" "$port_state" "$last_http_result"
    return 1
  fi
  service_state="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)"
  if [[ "$service_state" != "active" ]]; then
    health_diagnostics 'failed after local HTTP became ready' "$service_state" "$port_state" "$last_http_result"
    return 1
  fi
  curl --fail --silent --show-error --max-time 20 "$PUBLIC_URL" >/dev/null && public_ok=1
  curl --fail --silent --show-error --max-time 20 "${PUBLIC_URL%/}/login" >/dev/null && login_ok=1
  journal_output="$(journalctl -u "$SERVICE_NAME" --since "@$DEPLOY_STARTED_AT" --no-pager)" || return 1
  if grep -q 'Traceback (most recent call last)' <<< "$journal_output"; then
    return 1
  fi
  service_state="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)"
  if [[ "$service_state" != "active" ]]; then
    health_diagnostics 'failed during final checks' "$service_state" "$port_state" "$last_http_result"
    return 1
  fi
  [[ "$public_ok" -eq 1 && "$login_ok" -eq 1 ]]
}

write_deployed_manifest() {
  python3 - "$BUNDLE_DIR/artifact-manifest.json" "$RELEASE_DIR/deployed-manifest.json" <<'PY'
import json
import sys
from datetime import datetime, timezone

with open(sys.argv[1], encoding="utf-8") as file_handle:
    manifest = json.load(file_handle)
manifest["deployed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
with open(sys.argv[2], "w", encoding="utf-8") as file_handle:
    json.dump(manifest, file_handle, indent=2, sort_keys=True)
    file_handle.write("\n")
PY
}

rollback() {
  local rollback_ok=1
  local restore_tmp
  trap - ERR
  set +e
  printf 'Deployment failed; starting rollback. Failed release is preserved at %s\n' "$RELEASE_DIR" >&2
  if [[ "$SWITCHED" -eq 1 || "$DB_CHANGED" -eq 1 || "$SERVICE_STOPPED" -eq 1 ]]; then
    systemctl stop "$SERVICE_NAME" || rollback_ok=0
  fi
  if [[ "$SWITCHED" -eq 1 && -n "$PREVIOUS_RELEASE" ]]; then
    rm -f "$DEPLOY_ROOT/.current.rollback"
    if ln -s "$PREVIOUS_RELEASE" "$DEPLOY_ROOT/.current.rollback"; then
      mv -Tf "$DEPLOY_ROOT/.current.rollback" "$CURRENT_LINK" || rollback_ok=0
    else
      rollback_ok=0
    fi
  fi
  if [[ "$DB_CHANGED" -eq 1 && -n "$APP_DB_BACKUP" ]]; then
    restore_tmp="$CONFIG_DIR/.app.db.rollback.$COMMIT_SHA"
    rm -f "$restore_tmp"
    if cp --preserve=mode,timestamps "$APP_DB_BACKUP" "$restore_tmp"; then
      rm -f "$APP_DB-wal" "$APP_DB-shm" "$APP_DB-journal"
      if mv -f "$restore_tmp" "$APP_DB"; then
        restore_app_db_metadata || rollback_ok=0
      else
        rollback_ok=0
      fi
    else
      rollback_ok=0
    fi
  fi
  if [[ "$SWITCHED" -eq 1 || "$DB_CHANGED" -eq 1 || "$SERVICE_STOPPED" -eq 1 ]]; then
    systemctl restart "$SERVICE_NAME" || rollback_ok=0
    DEPLOY_STARTED_AT="$(date +%s)"
    export DEPLOY_STARTED_AT
    health_check || rollback_ok=0
  fi
  if [[ "$rollback_ok" -eq 1 ]]; then
    printf 'Rollback completed; original deployment remains failed\n' >&2
  else
    printf 'Rollback encountered errors; original deployment remains failed\n' >&2
  fi
  exit 1
}

print_dry_run_plan() {
  local current_theme
  current_theme="$(read_config_theme)"
  RELEASE_DIR="$RELEASES_DIR/$COMMIT_SHA"
  plan "would acquire flock on $DEPLOY_ROOT"
  plan "would run SQLite integrity check and back up app.db and gdrive.db"
  plan "would create candidate release $RELEASE_DIR with a clean venv"
  plan "would install and verify $WHEEL_FILENAME, run pip check and cps --help"
  plan 'would verify AU theme 3:aubooks and invite imports'
  if [[ "$current_theme" == "3" ]]; then
    printf 'CONFIG_THEME_ALREADY_3\n'
  else
    plan "would transactionally change config_theme from $current_theme to 3 after backup and candidate verification"
  fi
  plan "would atomically switch current from $PREVIOUS_RELEASE to $RELEASE_DIR"
  plan "would restart $SERVICE_NAME and run service, port, local HTTP, public HTTPS, login, and traceback checks"
  plan "would write deployed-manifest.json; on failure would restore DB and current symlink"
  printf 'ROLLBACK_PREVIOUS_RELEASE=%s\n' "$PREVIOUS_RELEASE"
}

if [[ "$DRY_RUN" -eq 0 ]]; then
  [[ -d "$DEPLOY_ROOT" && ! -L "$DEPLOY_ROOT" ]] || fail "deploy root is missing or unsafe: $DEPLOY_ROOT"
  acquire_lock
fi
validate_bundle
validate_platform
RELEASE_DIR="$RELEASES_DIR/$COMMIT_SHA"
[[ ! -e "$RELEASE_DIR" ]] || fail "release already exists: $RELEASE_DIR"

if [[ "$DRY_RUN" -eq 1 ]]; then
  print_dry_run_plan
  exit 0
fi

DEPLOY_STARTED=1
DEPLOY_STARTED_AT="$(date +%s)"
export DEPLOY_STARTED_AT
trap 'if [[ "$DEPLOY_STARTED" -eq 1 ]]; then rollback; fi' ERR

validate_app_database
backup_databases
create_candidate_release
set_aubooks_theme_if_needed
switch_current_release
restart_service
health_check
write_deployed_manifest
DEPLOY_STARTED=0
trap - ERR
printf 'Deployment completed: %s\n' "$COMMIT_SHA"
