#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE="aubooks-vps1-housekeeping.service"
TIMER="aubooks-vps1-housekeeping.timer"

mkdir -p -- "$UNIT_DIR"
ln -sfn -- "$SCRIPT_DIR/$SERVICE" "$UNIT_DIR/$SERVICE"
ln -sfn -- "$SCRIPT_DIR/$TIMER" "$UNIT_DIR/$TIMER"
systemctl --user daemon-reload
systemctl --user enable --now "$TIMER"
systemctl --user status "$TIMER" --no-pager
