#!/usr/bin/env bash
#
# update.sh — update Mnema to the latest version from GitHub
#
# Equivalent to the `mnema-update` command, usable on its own. Useful when
# you cloned the repo manually (didn't use install.sh) and want a one-shot
# updater.
#
#   ./scripts/update.sh
#
set -euo pipefail

# Resolve the repo root (parent of this script's directory).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PKG_DIR="$REPO_DIR/packages/mnema-python"

[[ -f "$PKG_DIR/pyproject.toml" ]] || {
  echo "✗ Could not find package at $PKG_DIR" >&2
  exit 1
}

BOLD='\033[1m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { printf "${BLUE}▸${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${NC} %s\n" "$*"; }

# Look for the venv created by install.sh first, then any local .venv.
if [[ -d "$HOME/.mnema-src/.venv" ]]; then
  VENV="$HOME/.mnema-src/.venv"
elif [[ -d "$REPO_DIR/.venv" ]]; then
  VENV="$REPO_DIR/.venv"
else
  VENV=""
fi

info "Pulling latest changes..."
git -C "$REPO_DIR" fetch --quiet
LOCAL="$(git -C "$REPO_DIR" rev-parse HEAD)"
REMOTE="$(git -C "$REPO_DIR" rev-parse '@{u}' 2>/dev/null || echo "$LOCAL")"

if [[ "$LOCAL" == "$REMOTE" ]]; then
  ok "Already up to date ($LOCAL)."
  exit 0
fi

git -C "$REPO_DIR" pull --ff-only
ok "Pulled new commits."

info "Reinstalling dependencies..."
cd "$PKG_DIR"
if [[ -n "$VENV" ]]; then
  VIRTUAL_ENV="$VENV" uv pip install -e '.[default]'
else
  # Fall back to uv tool install (creates its own isolated env).
  uv tool install --force -e '.[default]'
fi
ok "Reinstalled."

info "Verifying..."
if [[ -n "$VENV" ]]; then
  "$VENV/bin/python" -m mnema --doctor
else
  mnema --doctor
fi

printf '\n'
ok "Mnema is now at $(git -C "$REPO_DIR" describe --tags --always 2>/dev/null || echo latest)."
