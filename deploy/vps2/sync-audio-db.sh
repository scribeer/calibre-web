#!/bin/bash
# sync-audio-db.sh — VPS2 pulls audio.db snapshot from VPS1 via SSH/SCP.
#
# Runs as cron every minute. Creates consistent snapshot on VPS1 via
# SQLite VACUUM INTO to a unique temp path, transfers to VPS2, validates,
# and atomically replaces /opt/calibre-web/data/audio.db.
#
# Concurrency: flock prevents overlapping runs.
# Cleanup: remote temp is always deleted; local temp is always deleted;
#          previous working audio.db is preserved only on error;
#          on success the rollback file is removed.
#
# Environment:
#   AUBOOKS_SSH_HOST     — VPS1 IP/hostname (required)
#   AUBOOKS_SSH_USER     — SSH user on VPS1 (default: feninf)
#   AUBOOKS_SSH_KEY      — path to private key (default: /opt/calibre-web/config/ssh/aubooks_ed25519)
#   AUBOOKS_SSH_PORT     — VPS1 SSH port (default: 22)
#   AUBOOKS_KNOWN_HOSTS  — known_hosts file (default: /opt/calibre-web/config/ssh/known_hosts)
#   AUBOOKS_AUDIO_DB     — local target path (default: /opt/calibre-web/data/audio.db)
#   AUBOOKS_VPS1_AUDIO_DB — remote audio.db path (default: /home/feninf/aubooks/audio.db)
set -euo pipefail

SSH_HOST="${AUBOOKS_SSH_HOST:?AUBOOKS_SSH_HOST is required}"
SSH_USER="${AUBOOKS_SSH_USER:-feninf}"
SSH_KEY="${AUBOOKS_SSH_KEY:-/opt/calibre-web/config/ssh/aubooks_ed25519}"
SSH_PORT="${AUBOOKS_SSH_PORT:-22}"
KNOWN_HOSTS="${AUBOOKS_KNOWN_HOSTS:-/opt/calibre-web/config/ssh/known_hosts}"
TARGET="${AUBOOKS_AUDIO_DB:-/opt/calibre-web/data/audio.db}"
REMOTE_DB="${AUBOOKS_VPS1_AUDIO_DB:-/home/feninf/aubooks/audio.db}"
WORK_DIR="$(dirname "$TARGET")"
LOCK_FILE="${WORK_DIR}/.audio-sync.lock"
LOG_FILE="${WORK_DIR}/audio-sync.log"
TIMEOUT=30

mkdir -p "$WORK_DIR"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S%z')" "$*" >> "$LOG_FILE"; }

# Concurrency lock
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

SSH_OPTS=(
    -o BatchMode=yes
    -o ConnectTimeout=5
    -o StrictHostKeyChecking=yes
    -o UserKnownHostsFile="$KNOWN_HOSTS"
    -o "Port=$SSH_PORT"
    -i "$SSH_KEY"
)

CANDIDATE="${WORK_DIR}/.audio.db.candidate.$$"
ROLLBACK="${WORK_DIR}/.audio.db.rollback.$$"
REMOTE_SNAPSHOT=""
PROMOTED=0
OLD_MOVED=0

cleanup() {
    rm -f "$CANDIDATE" 2>/dev/null
    if [ "$OLD_MOVED" -eq 1 ] && [ "$PROMOTED" -eq 0 ] && [ -f "$ROLLBACK" ]; then
        mv -f "$ROLLBACK" "$TARGET" 2>/dev/null || true
    fi
    rm -f "$ROLLBACK" 2>/dev/null
    # Always remove remote snapshot
    if [ -n "$REMOTE_SNAPSHOT" ]; then
        timeout 10 ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" \
            "rm -f '$REMOTE_SNAPSHOT'" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# 1. Create unique remote temp path and consistent snapshot on VPS1
REMOTE_SNAPSHOT=$(timeout "$TIMEOUT" ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" \
    "python3 -c \"
import sqlite3, sys, tempfile, os
src = '${REMOTE_DB}'
if not os.path.exists(src):
    print('ERROR=source db not found', file=sys.stderr); sys.exit(1)
conn = sqlite3.connect(src)
try:
    backup = conn.execute('SELECT name FROM sqlite_master WHERE type=\\\"table\\\" AND name=\\\"audio\\\"').fetchone()
    if backup is None:
        print('ERROR=no audio table', file=sys.stderr); sys.exit(1)
    fd, path = tempfile.mkstemp(prefix='audio-sync-', suffix='.db', dir='/tmp')
    os.close(fd)
    conn.execute('VACUUM INTO \\\"' + path + '\\\"')
    print(path)
finally:
    conn.close()
\"" 2>/dev/null) || true

if [ -z "$REMOTE_SNAPSHOT" ]; then
    log "ERROR: snapshot creation failed on VPS1"
    exit 0
fi

# 2. SCP snapshot to VPS2
if ! timeout "$TIMEOUT" scp "${SSH_OPTS[@]}" \
    "${SSH_USER}@${SSH_HOST}:${REMOTE_SNAPSHOT}" \
    "$CANDIDATE" 2>/dev/null; then
    log "ERROR: SCP transfer failed"
    exit 0
fi

# 3. Validate candidate
if ! python3 -c "
import sqlite3, sys
conn = sqlite3.connect('file:${CANDIDATE}?mode=ro', uri=True, timeout=5)
try:
    r = conn.execute('PRAGMA integrity_check').fetchone()
    if r != ('ok',):
        print('integrity check failed', file=sys.stderr); sys.exit(1)
    cols = {row[1] for row in conn.execute('PRAGMA table_info(audio)')}
    required = {'book_id','job_id','requested_by_user_id','status','filename',
                'opendrive_path','sha256','filesize','duration','error',
                'created_at','updated_at'}
    missing = required - cols
    if missing:
        print('missing columns: ' + ', '.join(sorted(missing)), file=sys.stderr); sys.exit(1)
finally:
    conn.close()
" 2>/dev/null; then
    log "ERROR: candidate validation failed"
    exit 0
fi

# 4. Atomic replace
if [ -f "$TARGET" ]; then
    mv -f "$TARGET" "$ROLLBACK"
    OLD_MOVED=1
fi
if mv -f "$CANDIDATE" "$TARGET"; then
    chown calibreweb:calibreweb "$TARGET" 2>/dev/null || true
    chmod 644 "$TARGET" 2>/dev/null || true
    PROMOTED=1
    log "OK: audio.db updated"
else
    log "ERROR: atomic replace failed"
fi
