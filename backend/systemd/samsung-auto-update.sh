#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/paragon-av/Samsung-Display-Hub}"
BACKEND_DIR="$REPO_DIR/backend"
BACKEND_SERVICE="${BACKEND_SERVICE:-samsung-backend}"
AGENT_SERVICE="${AGENT_SERVICE:-samsung-option-b-agent}"

cd "$REPO_DIR"

CURRENT_COMMIT="$(git -c safe.directory="$REPO_DIR" rev-parse --short HEAD)"

git -c safe.directory="$REPO_DIR" fetch origin
REMOTE_COMMIT="$(git -c safe.directory="$REPO_DIR" rev-parse --short origin/main)"

if [[ "$CURRENT_COMMIT" == "$REMOTE_COMMIT" ]]; then
  echo "[auto-update] already up to date ($CURRENT_COMMIT)"
  exit 0
fi

echo "[auto-update] updating $CURRENT_COMMIT -> $REMOTE_COMMIT"
git -c safe.directory="$REPO_DIR" reset --hard origin/main

if [[ -f "$BACKEND_DIR/requirements.txt" && -x "$BACKEND_DIR/.venv/bin/pip" ]]; then
  "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
fi

systemctl restart "$BACKEND_SERVICE"
if systemctl list-unit-files | grep -q "^${AGENT_SERVICE}\.service"; then
  systemctl restart "$AGENT_SERVICE"
fi

echo "[auto-update] services restarted successfully"