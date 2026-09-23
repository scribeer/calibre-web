#!/usr/bin/env bash

set -uo pipefail
umask 077

MODE="dry-run"
case "${1:---dry-run}" in
  --dry-run) ;;
  --apply) MODE="apply" ;;
  *)
    printf 'Usage: %s [--dry-run|--apply]\n' "$0" >&2
    exit 2
    ;;
esac
[ "$#" -le 1 ] || { printf 'Usage: %s [--dry-run|--apply]\n' "$0" >&2; exit 2; }

BASE_AUBOOKS_DIR="${BASE_AUBOOKS_DIR:-$HOME/aubooks}"
GENERATIONS_DIR="${GENERATIONS_DIR:-$BASE_AUBOOKS_DIR/sync-export/generations}"
JOBS_DIR="${JOBS_DIR:-$BASE_AUBOOKS_DIR/jobs}"
EXPORT_LOCK_FILE="${EXPORT_LOCK_FILE:-$BASE_AUBOOKS_DIR/export-metadata-sync.lock}"
AUBOOK_REMOTE="${AUBOOK_REMOTE:-$HOME/bin/aubook-remote.sh}"
AUDIO_INDEX_RUNTIME="${AUDIO_INDEX_RUNTIME:-$HOME/bin/audio-index-runtime.py}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OPENCODE_BIN="${OPENCODE_BIN:-$HOME/.opencode/bin/opencode}"
OPENCODE_DB="${OPENCODE_DB:-$HOME/.local/share/opencode/opencode.db}"
TMP_ROOT="${TMP_ROOT:-/tmp}"
STATE_DIR="${HOUSEKEEPING_STATE_DIR:-$HOME/.local/state/aubooks}"
LOG_FILE="${HOUSEKEEPING_LOG_FILE:-$STATE_DIR/vps1-housekeeping.log}"
LOCK_FILE="${HOUSEKEEPING_LOCK_FILE:-${XDG_RUNTIME_DIR:-$STATE_DIR}/aubooks-vps1-housekeeping.lock}"
DF_TARGET="${HOUSEKEEPING_DF_TARGET:-$HOME}"
FTS_GENERATION="9345aa9df713b711698884e48bb5d415c741f3f299582319f026794dcd6c9a45"
MIB=$((1024 * 1024))
GIB=$((1024 * 1024 * 1024))
NORMAL_FREE_BYTES=$((8 * GIB))
PRESSURE_FREE_BYTES=$((6 * GIB))

mkdir -p -- "$STATE_DIR" "$(dirname "$LOCK_FILE")" || {
  printf 'ERROR cannot create housekeeping state directory\n' >&2
  exit 1
}
[ -d "$STATE_DIR" ] && [ ! -L "$STATE_DIR" ] \
  && [ "$(readlink -f -- "$STATE_DIR" 2>/dev/null)" = "$STATE_DIR" ] || {
  printf 'ERROR unsafe housekeeping state directory: %s\n' "$STATE_DIR" >&2
  exit 1
}
[ -d "$(dirname "$LOCK_FILE")" ] && [ ! -L "$(dirname "$LOCK_FILE")" ] \
  && [ "$(readlink -f -- "$(dirname "$LOCK_FILE")" 2>/dev/null)" = "$(dirname "$LOCK_FILE")" ] || {
  printf 'ERROR unsafe housekeeping lock directory: %s\n' "$(dirname "$LOCK_FILE")" >&2
  exit 1
}
[ ! -L "$LOCK_FILE" ] || {
  printf 'ERROR unsafe housekeeping lock symlink: %s\n' "$LOCK_FILE" >&2
  exit 1
}
exec 9>"$LOCK_FILE"
[ "$LOCK_FILE" -ef "/proc/$$/fd/9" ] || {
  printf 'ERROR housekeeping lock inode changed: %s\n' "$LOCK_FILE" >&2
  exit 1
}
if ! flock -n 9; then
  printf 'SKIP housekeeping: another instance holds %s\n' "$LOCK_FILE"
  exit 0
fi

if [ -f "$LOG_FILE" ]; then
  log_size="$(stat -c %s -- "$LOG_FILE" 2>/dev/null || printf '0')"
  if [[ "$log_size" =~ ^[0-9]+$ ]] && [ "$log_size" -gt "$MIB" ]; then
    mv -f -- "$LOG_FILE" "$LOG_FILE.1" || {
      printf 'ERROR cannot rotate %s\n' "$LOG_FILE" >&2
      exit 1
    }
  fi
fi
exec > >(tee -a "$LOG_FILE") 2>&1

RUN_FAILED=0

timestamp() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

dir_bytes() {
  du -sb -- "$1" 2>/dev/null | cut -f1
}

file_bytes() {
  if [ -f "$1" ]; then
    stat -c %s -- "$1" 2>/dev/null || printf '0\n'
  else
    printf '0\n'
  fi
}

free_bytes() {
  if [ -n "${HOUSEKEEPING_FREE_BYTES_OVERRIDE:-}" ]; then
    printf '%s\n' "$HOUSEKEEPING_FREE_BYTES_OVERRIDE"
    return
  fi
  df -B1 --output=avail "$1" 2>/dev/null | tail -n 1 | tr -dc '0-9'
  printf '\n'
}

PRESSURE_LEVEL="normal"
if [ -n "${HOUSEKEEPING_FREE_BYTES_OVERRIDE:-}" ]; then
  CURRENT_FREE_BYTES="$HOUSEKEEPING_FREE_BYTES_OVERRIDE"
else
  CURRENT_FREE_BYTES="$(free_bytes "$DF_TARGET" 2>/dev/null || true)"
fi
if [[ "$CURRENT_FREE_BYTES" =~ ^[0-9]+$ ]]; then
  if [ "$CURRENT_FREE_BYTES" -lt "$PRESSURE_FREE_BYTES" ]; then
    PRESSURE_LEVEL="critical"
  elif [ "$CURRENT_FREE_BYTES" -lt "$NORMAL_FREE_BYTES" ]; then
    PRESSURE_LEVEL="pressure"
  fi
fi

if [ -n "${HOUSEKEEPING_CACHE_ROOTS:-}" ]; then
  IFS=: read -r -a CACHE_ROOTS <<< "$HOUSEKEEPING_CACHE_ROOTS"
else
  CACHE_ROOTS=(
    "$HOME/.cache/pip"
    "$HOME/.cache/huggingface"
    "$HOME/.cache/torch"
    "$HOME/.cache/uv"
    "$HOME/.cache/datalab/models"
  )
fi

root_is_safe() {
  local root="$1" resolved
  [ -d "$root" ] && [ ! -L "$root" ] || return 1
  resolved="$(readlink -f -- "$root" 2>/dev/null)" || return 1
  [ "$resolved" = "$root" ]
}

direct_child_is_safe() {
  local root="$1" target="$2" root_real target_real
  root_is_safe "$root" || return 1
  [ -d "$target" ] && [ ! -L "$target" ] || return 1
  [ "$(dirname -- "$target")" = "$root" ] || return 1
  root_real="$(readlink -f -- "$root" 2>/dev/null)" || return 1
  target_real="$(readlink -f -- "$target" 2>/dev/null)" || return 1
  [ "$(dirname -- "$target_real")" = "$root_real" ] || return 1
  [ "$target_real" = "$root_real/$(basename -- "$target")" ]
}

direct_entry_is_safe() {
  local root="$1" target="$2" root_real target_real
  root_is_safe "$root" || return 1
  [ -e "$target" ] && [ ! -L "$target" ] || return 1
  [ "$(dirname -- "$target")" = "$root" ] || return 1
  root_real="$(readlink -f -- "$root" 2>/dev/null)" || return 1
  target_real="$(readlink -f -- "$target" 2>/dev/null)" || return 1
  [ "$(dirname -- "$target_real")" = "$root_real" ]
}

job_child_is_safe() {
  local root="$1" target="$2" root_real target_real
  root_is_safe "$root" || return 1
  [ -e "$target" ] || return 1
  [ ! -L "$target" ] || return 1
  [ "$(dirname -- "$target")" = "$root" ] || return 1
  root_real="$(readlink -f -- "$root" 2>/dev/null)" || return 1
  target_real="$(readlink -f -- "$target" 2>/dev/null)" || return 1
  [ "$(dirname -- "$target_real")" = "$root_real" ]
}

job_has_live_process() {
  local job="$1" id="$2" key pid boot cmdline
  for key in RUNNER_PID PID SETUP_PID; do
    pid="$(grep -m1 "^${key}=" "$job/status" 2>/dev/null | cut -d= -f2-)"
    [[ "$pid" =~ ^[1-9][0-9]*$ ]] || continue
    [ -r "/proc/$pid/cmdline" ] || continue
    boot="$(grep -m1 "^${key}_BOOT_ID=" "$job/status" 2>/dev/null | cut -d= -f2-)"
    [ -z "$boot" ] || [ "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)" = "$boot" ] || continue
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    case "$cmdline" in
      *"$AUBOOK_REMOTE"*"$id"*) return 0 ;;
    esac
  done
  return 1
}

job_has_recent_heartbeat() {
  local job="$1" heartbeat now age
  heartbeat="$(cat "$job/heartbeat" 2>/dev/null || true)"
  [[ "$heartbeat" =~ ^[0-9]+$ ]] || return 1
  now="$(date +%s)"
  age=$((now - heartbeat))
  [ "$age" -ge 0 ] && [ "$age" -lt 180 ]
}

path_is_in_use() {
  local target="$1"
  [ -S "$target" ] && return 0
  command -v fuser >/dev/null 2>&1 && fuser -s -- "$target" 2>/dev/null
}

path_tree_is_in_use() {
  local target="$1" child
  path_is_in_use "$target" && return 0
  [ -d "$target" ] || return 1
  while IFS= read -r -d '' child; do
    if path_is_in_use "$child"; then
      return 0
    fi
  done < <(find -- "$target" -type f -print0 2>/dev/null)
  return 1
}

remove_entry() {
  local section="$1" root="$2" target="$3" size
  if ! direct_entry_is_safe "$root" "$target"; then
    printf '%s SKIP unsafe path: %s\n' "$section" "$target"
    return 1
  fi
  if path_tree_is_in_use "$target"; then
    printf '%s KEEP active/in-use %s\n' "$section" "$target"
    return 1
  fi
  size="$(du -sb -- "$target" 2>/dev/null | cut -f1)"
  [[ "$size" =~ ^[0-9]+$ ]] || size=0
  if [ "$MODE" = "apply" ]; then
    if rm -rf -- "$target"; then
      printf '%s DELETE %s bytes=%s\n' "$section" "$target" "$size"
      LAST_REMOVED_BYTES="$size"
      return 0
    fi
    printf '%s ERROR delete failed: %s\n' "$section" "$target"
    RUN_FAILED=1
    return 1
  fi
  printf '%s DELETE(dry-run) %s bytes=%s\n' "$section" "$target" "$size"
  LAST_REMOVED_BYTES="$size"
  return 0
}

remove_directory() {
  local section="$1" root="$2" target="$3" size
  if ! direct_child_is_safe "$root" "$target"; then
    printf '%s SKIP unsafe path: %s\n' "$section" "$target"
    return 1
  fi
  size="$(dir_bytes "$target")"
  [[ "$size" =~ ^[0-9]+$ ]] || size=0
  if [ "$MODE" = "apply" ]; then
    if rm -rf -- "$target"; then
      printf '%s DELETE %s bytes=%s\n' "$section" "$target" "$size"
      LAST_REMOVED_BYTES="$size"
      return 0
    fi
    printf '%s ERROR delete failed: %s\n' "$section" "$target"
    RUN_FAILED=1
    return 1
  fi
  printf '%s DELETE(dry-run) %s bytes=%s\n' "$section" "$target" "$size"
  LAST_REMOVED_BYTES="$size"
  return 0
}

cleanup_job_payload() {
  local section="$1" job="$2" freed=0 child before after
  before="$(dir_bytes "$job")"
  for child in "$job/work" "$job/out" "$job"/source.* "$job/source_path" \
    "$job/heartbeat" "$job/heartbeat.stop" "$job/LOW_DISK_ABORT"; do
    [ -e "$child" ] || continue
    if ! job_child_is_safe "$job" "$child"; then
      printf '%s SKIP unsafe job payload: %s\n' "$section" "$child"
      RUN_FAILED=1
      continue
    fi
    if [ "$MODE" = "apply" ]; then
      if ! rm -rf -- "$child"; then
        printf '%s ERROR payload delete failed: %s\n' "$section" "$child"
        RUN_FAILED=1
      fi
    else
      printf '%s DELETE(dry-run) %s\n' "$section" "$child"
    fi
  done
  after="$(dir_bytes "$job")"
  [[ "$before" =~ ^[0-9]+$ ]] || before=0
  [[ "$after" =~ ^[0-9]+$ ]] || after=0
  if [ "$MODE" = "apply" ]; then
    freed=$((before - after))
    [ "$freed" -ge 0 ] || freed=0
    printf '%s DELETE payload job=%s bytes=%s\n' "$section" "$job" "$freed"
  else
    freed="$before"
    printf '%s DELETE(dry-run) payload job=%s bytes=%s\n' "$section" "$job" "$freed"
  fi
  LAST_REMOVED_BYTES="$freed"
}

show_df() {
  local label="$1"
  printf '%s\n' "$label"
  df -h -- "$DF_TARGET" 2>&1 || printf 'WARNING df failed for %s\n' "$DF_TARGET"
}

cleanup_sync_export() {
  local section="sync-export" freed=0 candidate name mtime i newest_index oldest_index
  local -a generations=() mtimes=()
  local -A keep=()
  printf '\n[%s]\n' "$section"
  if ! root_is_safe "$GENERATIONS_DIR"; then
    printf '%s SKIP unsafe or missing root: %s\n' "$section" "$GENERATIONS_DIR"
    printf '%s freed_bytes=0\n' "$section"
    return
  fi
  if [ ! -f "$EXPORT_LOCK_FILE" ] || [ -L "$EXPORT_LOCK_FILE" ]; then
    printf '%s SKIP export lock is unavailable or unsafe: %s\n' "$section" "$EXPORT_LOCK_FILE"
    printf '%s freed_bytes=0\n' "$section"
    return
  fi
  exec 7<>"$EXPORT_LOCK_FILE"
  if [ ! "$EXPORT_LOCK_FILE" -ef "/proc/$$/fd/7" ]; then
    printf '%s SKIP export lock inode changed: %s\n' "$section" "$EXPORT_LOCK_FILE"
    printf '%s freed_bytes=0\n' "$section"
    exec 7>&-
    return
  fi
  if ! flock -n -x 7; then
    printf '%s SKIP metadata export is running\n' "$section"
    printf '%s freed_bytes=0\n' "$section"
    exec 7>&-
    return
  fi

  shopt -s nullglob
  for candidate in "$GENERATIONS_DIR"/*; do
    name="$(basename -- "$candidate")"
    if [ -L "$candidate" ]; then
      printf '%s KEEP symlink %s\n' "$section" "$candidate"
    elif [ ! -d "$candidate" ]; then
      printf '%s KEEP non-directory %s\n' "$section" "$candidate"
    elif [[ ! "$name" =~ ^[0-9a-f]{64}$ ]]; then
      printf '%s KEEP unrecognized directory %s\n' "$section" "$candidate"
    elif ! direct_child_is_safe "$GENERATIONS_DIR" "$candidate"; then
      printf '%s KEEP unsafe directory %s\n' "$section" "$candidate"
    else
      mtime="$(stat -c %Y -- "$candidate" 2>/dev/null || true)"
      if [[ "$mtime" =~ ^[0-9]+$ ]]; then
        generations+=("$candidate")
        mtimes+=("$mtime")
      else
        printf '%s KEEP unreadable mtime %s\n' "$section" "$candidate"
      fi
    fi
  done
  shopt -u nullglob

  for _ in 1 2; do
    newest_index=-1
    for i in "${!generations[@]}"; do
      [ -z "${keep[${generations[$i]}]:-}" ] || continue
      if [ "$newest_index" -lt 0 ] \
        || [ "${mtimes[$i]}" -gt "${mtimes[$newest_index]}" ] \
        || { [ "${mtimes[$i]}" -eq "${mtimes[$newest_index]}" ] \
          && [[ "${generations[$i]}" > "${generations[$newest_index]}" ]]; }; then
        newest_index="$i"
      fi
    done
    [ "$newest_index" -ge 0 ] || break
    keep["${generations[$newest_index]}"]=1
  done
  keep["$GENERATIONS_DIR/$FTS_GENERATION"]=1

  for candidate in "${generations[@]}"; do
    if [ -n "${keep[$candidate]:-}" ]; then
      printf '%s KEEP generation %s\n' "$section" "$candidate"
      continue
    fi
    LAST_REMOVED_BYTES=0
    if remove_directory "$section" "$GENERATIONS_DIR" "$candidate"; then
      freed=$((freed + LAST_REMOVED_BYTES))
    fi
  done
  flock -u 7
  exec 7>&-
  printf '%s freed_bytes=%s mode=%s\n' "$section" "$freed" "$MODE"
}

unique_field() {
  local text="$1" key="$2" line count=0
  FIELD_VALUE=""
  while IFS= read -r line; do
    case "$line" in
      "$key="*) FIELD_VALUE="${line#*=}"; count=$((count + 1)) ;;
    esac
  done <<< "$text"
  FIELD_COUNT="$count"
  [ "$count" -eq 1 ]
}

durable_status_for_job() {
  local job="$1" id="$2" book_id submission_id output parsed
  DURABLE_STATUS="unknown"
  unique_field "$LOCAL_STATUS" BOOK_ID || true
  [ "$FIELD_COUNT" -le 1 ] || return 1
  book_id="$FIELD_VALUE"
  unique_field "$LOCAL_STATUS" SUBMISSION_ID || true
  [ "$FIELD_COUNT" -le 1 ] || return 1
  submission_id="$FIELD_VALUE"
  if [ -n "$book_id" ] && [ -z "$submission_id" ]; then
    [[ "$book_id" =~ ^[1-9][0-9]*$ ]] || return 1
    output="$("$PYTHON_BIN" "$AUDIO_INDEX_RUNTIME" exact-status "$book_id" "$id" 2>/dev/null)" || return 1
    unique_field "$output" EXACT_STATUS || return 1
    case "$FIELD_VALUE" in
      queued|processing|ready|failed|cancelled) DURABLE_STATUS="$FIELD_VALUE"; return 0 ;;
      *) return 1 ;;
    esac
  fi
  if [ -n "$submission_id" ] && [ -z "$book_id" ]; then
    [[ "$submission_id" =~ ^[A-Za-z0-9_-]+$ ]] || return 1
    output="$("$PYTHON_BIN" "$AUDIO_INDEX_RUNTIME" submission-get "$submission_id" 2>/dev/null)" || return 1
    parsed="$("$PYTHON_BIN" -c '
import json
import sys

expected_job_id = sys.argv[1]
try:
    value = json.loads(sys.argv[2])
except (json.JSONDecodeError, OSError):
    raise SystemExit(1)
if not isinstance(value, dict):
    raise SystemExit(1)
status = value.get("status")
job_id = value.get("job_id")
if job_id != expected_job_id or status not in {"queued", "processing", "ready", "failed", "cancelled"}:
    raise SystemExit(1)
print(status)
' "$id" "$output")" || return 1
    DURABLE_STATUS="$parsed"
    return 0
  fi
  return 1
}

cleanup_tts_jobs() {
  local section="tts-jobs" freed=0 job id output state status_mtime age now expected eligible
  printf '\n[%s]\n' "$section"
  if ! root_is_safe "$JOBS_DIR"; then
    printf '%s SKIP unsafe or missing root: %s\n' "$section" "$JOBS_DIR"
    printf '%s freed_bytes=0\n' "$section"
    return
  fi
  if [ ! -x "$AUBOOK_REMOTE" ] || [ ! -f "$AUDIO_INDEX_RUNTIME" ]; then
    printf '%s SKIP runtime status commands unavailable\n' "$section"
    printf '%s freed_bytes=0\n' "$section"
    return
  fi
  now="$(date +%s)"
  shopt -s nullglob
  for job in "$JOBS_DIR"/*; do
    [ -d "$job" ] || continue
    id="$(basename -- "$job")"
    if [ -L "$job" ] || ! direct_child_is_safe "$JOBS_DIR" "$job"; then
      printf '%s KEEP unsafe/symlink %s\n' "$section" "$job"
      continue
    fi
    if [[ ! "$id" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]] || [[ "$id" == *..* ]]; then
      printf '%s KEEP invalid job id %s\n' "$section" "$job"
      continue
    fi
    if [ ! -f "$job/status" ] || [ -L "$job/status" ] \
      || [ ! -f "$job/control.lock" ] || [ -L "$job/control.lock" ]; then
      printf '%s KEEP incomplete/unsafe job metadata %s\n' "$section" "$job"
      continue
    fi
    exec 8<>"$job/control.lock"
    if ! flock -n -x 8; then
      printf '%s KEEP locked/active %s\n' "$section" "$job"
      exec 8>&-
      continue
    fi
    output="$("$AUBOOK_REMOTE" status "$id" 2>/dev/null)" || {
      printf '%s KEEP unreadable state %s\n' "$section" "$job"
      flock -u 8; exec 8>&-; continue
    }
    LOCAL_STATUS="$output"
    if ! unique_field "$LOCAL_STATUS" STATE; then
      printf '%s KEEP unknown state %s\n' "$section" "$job"
      flock -u 8; exec 8>&-; continue
    fi
    state="$FIELD_VALUE"
    case "$state" in
      RUNNING|QUEUED)
        printf '%s KEEP active state=%s %s\n' "$section" "$state" "$job"
        flock -u 8; exec 8>&-; continue
        ;;
      INTERRUPTED|FAILED|CANCELLED|DONE) ;;
      *)
        printf '%s KEEP unknown state=%s %s\n' "$section" "$state" "$job"
        flock -u 8; exec 8>&-; continue
        ;;
    esac
    if job_has_live_process "$job" "$id" || job_has_recent_heartbeat "$job"; then
      printf '%s KEEP active evidence state=%s %s\n' "$section" "$state" "$job"
      flock -u 8; exec 8>&-; continue
    fi
    if ! durable_status_for_job "$job" "$id"; then
      printf '%s KEEP unknown durable state local=%s %s\n' "$section" "$state" "$job"
      flock -u 8; exec 8>&-; continue
    fi
    if [ "$DURABLE_STATUS" = "processing" ] || [ "$DURABLE_STATUS" = "queued" ]; then
      printf '%s KEEP durable=%s local=%s %s\n' "$section" "$DURABLE_STATUS" "$state" "$job"
      flock -u 8; exec 8>&-; continue
    fi
    status_mtime="$(stat -c %Y -- "$job/status" 2>/dev/null || true)"
    if [[ ! "$status_mtime" =~ ^[0-9]+$ ]] || [ "$status_mtime" -gt "$now" ]; then
      printf '%s KEEP invalid age %s\n' "$section" "$job"
      flock -u 8; exec 8>&-; continue
    fi
    age=$((now - status_mtime))
    eligible=0
    case "$state" in
      DONE)
        expected="ready"
        [ "$DURABLE_STATUS" = "$expected" ] || {
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        }
        [ "$PRESSURE_LEVEL" != "normal" ] || [ "$age" -gt $((24 * 3600)) ] || {
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        }
        eligible=1
        ;;
      INTERRUPTED)
        [ "$DURABLE_STATUS" = "failed" ] || {
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        }
        [ "$PRESSURE_LEVEL" != "normal" ] || [ "$age" -gt $((72 * 3600)) ] || {
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        }
        eligible=1
        ;;
      FAILED)
        [ "$DURABLE_STATUS" = "failed" ] || {
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        }
        [ "$PRESSURE_LEVEL" != "normal" ] || [ "$age" -gt $((72 * 3600)) ] || {
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        }
        eligible=1
        ;;
      CANCELLED)
        if [ "$DURABLE_STATUS" != "cancelled" ] || [ ! -f "$job/CANCEL_COMPLETE" ] \
          || [ -L "$job/CANCEL_COMPLETE" ] \
          || { [ "$PRESSURE_LEVEL" = "normal" ] && [ "$age" -le $((72 * 3600)) ]; }; then
          printf '%s KEEP state=%s durable=%s age_seconds=%s %s\n' "$section" "$state" "$DURABLE_STATUS" "$age" "$job"
          flock -u 8; exec 8>&-; continue
        fi
        eligible=1
        ;;
    esac
    [ "$eligible" -eq 1 ] || { flock -u 8; exec 8>&-; continue; }
    LAST_REMOVED_BYTES=0
    cleanup_job_payload "$section" "$job"
    if [ "$LAST_REMOVED_BYTES" -gt 0 ]; then
      freed=$((freed + LAST_REMOVED_BYTES))
    fi
    flock -u 8
    exec 8>&-
  done
  shopt -u nullglob
  printf '%s freed_bytes=%s mode=%s\n' "$section" "$freed" "$MODE"
}

opencode_session_count() {
  "$PYTHON_BIN" -c 'import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else "unknown")' 2>/dev/null
}

cleanup_opencode() {
  local section="opencode" db_before wal_before free_before db_after wal_after free_after
  local json_file candidates_file session_count deleted=0 candidate required count_after
  printf '\n[%s]\n' "$section"
  db_before="$(file_bytes "$OPENCODE_DB")"
  wal_before="$(file_bytes "$OPENCODE_DB-wal")"
  free_before="$(free_bytes "$(dirname -- "$OPENCODE_DB")")"
  printf '%s before db_bytes=%s wal_bytes=%s sessions=not-read free_bytes=%s\n' \
    "$section" "$db_before" "$wal_before" "${free_before:-unknown}"
  if [[ ! "$db_before" =~ ^[0-9]+$ ]] || [ "$db_before" -le $((768 * MIB)) ]; then
    printf '%s KEEP database threshold_not_exceeded\n' "$section"
    printf '%s after db_bytes=%s wal_bytes=%s sessions=not-read deleted_sessions=0 free_bytes=%s\n' \
      "$section" "$db_before" "$wal_before" "${free_before:-unknown}"
    printf '%s freed_bytes=0 mode=%s\n' "$section" "$MODE"
    return
  fi
  if [ ! -x "$OPENCODE_BIN" ]; then
    printf '%s SKIP OpenCode CLI unavailable: %s\n' "$section" "$OPENCODE_BIN"
    printf '%s freed_bytes=0 mode=%s\n' "$section" "$MODE"
    return
  fi
  json_file="$(mktemp "$STATE_DIR/.housekeeping-sessions.XXXXXX")" || {
    printf '%s SKIP cannot create temporary session list\n' "$section"; return;
  }
  candidates_file="$(mktemp "$STATE_DIR/.housekeeping-candidates.XXXXXX")" || {
    rm -f -- "$json_file"; printf '%s SKIP cannot create candidate list\n' "$section"; return;
  }
  if ! "$OPENCODE_BIN" session list --format json -n 1000000 >"$json_file"; then
    printf '%s SKIP session list failed\n' "$section"
    rm -f -- "$json_file" "$candidates_file"
    return
  fi
  if ! session_count="$("$PYTHON_BIN" - "$json_file" "$candidates_file" <<'PY'
import json
import re
import sys
import time

source, destination = sys.argv[1:]
try:
    with open(source, encoding="utf-8") as stream:
        sessions = json.load(stream)
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
if not isinstance(sessions, list):
    raise SystemExit(1)
seen = set()
validated = []
for session in sessions:
    if not isinstance(session, dict):
        raise SystemExit(1)
    session_id = session.get("id")
    created = session.get("created")
    updated = session.get("updated")
    if (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", session_id)
            or session_id in seen or not isinstance(created, int) or isinstance(created, bool)
            or not isinstance(updated, int) or isinstance(updated, bool)
            or created <= 0 or updated <= 0):
        raise SystemExit(1)
    seen.add(session_id)
    validated.append((updated, created, session_id))
validated.sort(reverse=True)
cutoff_ms = int(time.time() * 1000) - 30 * 24 * 60 * 60 * 1000
with open(destination, "w", encoding="utf-8") as stream:
    for updated, _created, session_id in validated[100:]:
        if updated < cutoff_ms:
            stream.write(session_id + "\n")
print(len(validated))
PY
  )"; then
    printf '%s SKIP malformed session JSON; no sessions deleted\n' "$section"
    rm -f -- "$json_file" "$candidates_file"
    printf '%s freed_bytes=0 mode=%s\n' "$section" "$MODE"
    return
  fi
  printf '%s sessions_before=%s\n' "$section" "$session_count"
  if [ ! -s "$candidates_file" ]; then
    printf '%s KEEP no sessions satisfy age and newest-100 policy\n' "$section"
  fi
  while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    printf '%s DELETE%s session=%s\n' "$section" "$([ "$MODE" = "apply" ] || printf '(dry-run)')" "$candidate"
    if [ "$MODE" = "apply" ]; then
      if ! "$OPENCODE_BIN" session delete "$candidate"; then
        printf '%s ERROR session deletion failed; stopping OpenCode cleanup session=%s\n' "$section" "$candidate"
        rm -f -- "$json_file" "$candidates_file"
        RUN_FAILED=1
        return
      fi
      deleted=$((deleted + 1))
    fi
  done < "$candidates_file"

  if [ "$MODE" = "apply" ] && [ "$deleted" -gt 0 ]; then
    if ! "$OPENCODE_BIN" db 'PRAGMA wal_checkpoint(TRUNCATE);'; then
      printf '%s WARNING WAL checkpoint failed; VACUUM skipped\n' "$section"
      RUN_FAILED=1
    else
      db_after="$(file_bytes "$OPENCODE_DB")"
      free_after="$(free_bytes "$(dirname -- "$OPENCODE_DB")")"
      required=$((db_after * 2 + GIB))
      if [[ "$free_after" =~ ^[0-9]+$ ]] && [ "$free_after" -ge "$required" ]; then
        if ! "$OPENCODE_BIN" db 'VACUUM;'; then
          printf '%s WARNING VACUUM failed\n' "$section"
          RUN_FAILED=1
        fi
      else
        printf '%s WARNING VACUUM skipped: free_bytes=%s required_bytes=%s\n' \
          "$section" "${free_after:-unknown}" "$required"
      fi
    fi
  elif [ "$MODE" = "dry-run" ]; then
    printf '%s KEEP dry-run: checkpoint and VACUUM not executed\n' "$section"
  else
    printf '%s KEEP no sessions deleted: checkpoint and VACUUM not executed\n' "$section"
  fi

  db_after="$(file_bytes "$OPENCODE_DB")"
  wal_after="$(file_bytes "$OPENCODE_DB-wal")"
  free_after="$(free_bytes "$(dirname -- "$OPENCODE_DB")")"
  count_after="$session_count"
  if [ "$MODE" = "apply" ]; then
    if "$OPENCODE_BIN" session list --format json -n 1000000 >"$json_file"; then
      count_after="$(opencode_session_count < "$json_file")"
    else
      count_after="unknown"
    fi
  fi
  printf '%s after db_bytes=%s wal_bytes=%s sessions=%s deleted_sessions=%s free_bytes=%s\n' \
    "$section" "$db_after" "$wal_after" "$count_after" "$deleted" "${free_after:-unknown}"
  if [ "$MODE" = "apply" ] && [ "$((db_before + wal_before))" -gt "$((db_after + wal_after))" ]; then
    printf '%s freed_bytes=%s mode=%s\n' "$section" \
      "$((db_before + wal_before - db_after - wal_after))" "$MODE"
  elif [ "$MODE" = "dry-run" ]; then
    printf '%s freed_bytes=unknown mode=%s reason=session storage requires CLI deletion and VACUUM\n' "$section" "$MODE"
  else
    printf '%s freed_bytes=0 mode=%s\n' "$section" "$MODE"
  fi
  rm -f -- "$json_file" "$candidates_file"
}

cleanup_tmp() {
  local section="tmp" freed=0 candidate age now mtime max_age
  local -A seen=()
  printf '\n[%s]\n' "$section"
  if ! root_is_safe "$TMP_ROOT"; then
    printf '%s SKIP unsafe or missing root: %s\n' "$section" "$TMP_ROOT"
    printf '%s freed_bytes=0\n' "$section"
    return
  fi
  now="$(date +%s)"
  max_age=$((48 * 3600))
  [ "$PRESSURE_LEVEL" = "critical" ] && max_age=$((24 * 3600))
  shopt -s nullglob
  for candidate in "$TMP_ROOT"/aubooks-*-deploy.* \
    "$TMP_ROOT"/flibusta-calibre-test.* \
    "$TMP_ROOT"/calibre_test_* \
    "$TMP_ROOT"/calibre_smoke_* \
    "$TMP_ROOT"/opencode-*; do
    [ -z "${seen[$candidate]:-}" ] || continue
    seen["$candidate"]=1
    if [ -L "$candidate" ] || ! direct_entry_is_safe "$TMP_ROOT" "$candidate"; then
      printf '%s KEEP unsafe/symlink/non-directory %s\n' "$section" "$candidate"
      continue
    fi
    mtime="$(stat -c %Y -- "$candidate" 2>/dev/null || true)"
    if [[ ! "$mtime" =~ ^[0-9]+$ ]] || [ "$mtime" -gt "$now" ]; then
      printf '%s KEEP invalid age %s\n' "$section" "$candidate"
      continue
    fi
    age=$((now - mtime))
    if [ "$age" -le "$max_age" ]; then
      printf '%s KEEP recent age_seconds=%s %s\n' "$section" "$age" "$candidate"
      continue
    fi
    LAST_REMOVED_BYTES=0
    if remove_entry "$section" "$TMP_ROOT" "$candidate"; then
      freed=$((freed + LAST_REMOVED_BYTES))
    fi
  done
  shopt -u nullglob
  printf '%s freed_bytes=%s mode=%s\n' "$section" "$freed" "$MODE"
}

cleanup_caches() {
  local section="caches" root candidate age now mtime max_age freed=0 opencode_cache
  local -A seen=()
  printf '\n[%s]\n' "$section"
  max_age=$((7 * 24 * 3600))
  [ "$PRESSURE_LEVEL" != "normal" ] && max_age=0
  now="$(date +%s)"
  for root in "${CACHE_ROOTS[@]}"; do
    if ! root_is_safe "$root"; then
      printf '%s KEEP missing/unsafe root %s\n' "$section" "$root"
      continue
    fi
    shopt -s nullglob
    for candidate in "$root"/* "$root"/.*; do
      [ -z "${seen[$candidate]:-}" ] || continue
      seen["$candidate"]=1
      case "$(basename -- "$candidate")" in
        .|..|*.lock) continue ;;
      esac
      if ! direct_entry_is_safe "$root" "$candidate"; then
        printf '%s KEEP unsafe %s\n' "$section" "$candidate"
        continue
      fi
      mtime="$(stat -c %Y -- "$candidate" 2>/dev/null || true)"
      if [[ ! "$mtime" =~ ^[0-9]+$ ]] || [ "$mtime" -gt "$now" ]; then
        printf '%s KEEP invalid age %s\n' "$section" "$candidate"
        continue
      fi
      age=$((now - mtime))
      if [ "$age" -le "$max_age" ]; then
        printf '%s KEEP recent age_seconds=%s %s\n' "$section" "$age" "$candidate"
        continue
      fi
      LAST_REMOVED_BYTES=0
      if remove_entry "$section" "$root" "$candidate"; then
        freed=$((freed + LAST_REMOVED_BYTES))
      fi
    done
    shopt -u nullglob
  done
  opencode_cache="$HOME/.cache/opencode"
  if root_is_safe "$opencode_cache"; then
    shopt -s nullglob
    for candidate in "$opencode_cache"/*.tmp; do
      if ! direct_entry_is_safe "$opencode_cache" "$candidate"; then
        printf '%s KEEP unsafe %s\n' "$section" "$candidate"
        continue
      fi
      mtime="$(stat -c %Y -- "$candidate" 2>/dev/null || true)"
      if [[ ! "$mtime" =~ ^[0-9]+$ ]]; then
        printf '%s KEEP invalid age %s\n' "$section" "$candidate"
        continue
      fi
      age=$((now - mtime))
      if [ "$age" -le "$max_age" ]; then
        printf '%s KEEP recent age_seconds=%s %s\n' "$section" "$age" "$candidate"
        continue
      fi
      LAST_REMOVED_BYTES=0
      if remove_entry "$section" "$opencode_cache" "$candidate"; then
        freed=$((freed + LAST_REMOVED_BYTES))
      fi
    done
    shopt -u nullglob
  fi
  printf '%s freed_bytes=%s mode=%s\n' "$section" "$freed" "$MODE"
}

printf 'START timestamp=%s mode=%s pid=%s\n' "$(timestamp)" "$MODE" "$$"
printf 'WATERMARK free_bytes=%s level=%s normal_min=%s pressure_min=%s\n' \
  "${CURRENT_FREE_BYTES:-unknown}" "$PRESSURE_LEVEL" "$NORMAL_FREE_BYTES" "$PRESSURE_FREE_BYTES"
show_df 'DF BEFORE'
cleanup_sync_export
cleanup_tts_jobs
cleanup_opencode
cleanup_tmp
cleanup_caches
show_df 'DF AFTER'
printf 'DONE timestamp=%s mode=%s\n' "$(timestamp)" "$MODE"
exit "$RUN_FAILED"
