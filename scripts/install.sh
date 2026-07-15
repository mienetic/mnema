#!/usr/bin/env bash
#
# install.sh — one-line installer for Mnema (MCP × Vector DB for AI memory)
#
# What it does:
#   1. Installs `uv` (fast Python package manager) if missing
#   2. Clones the Mnema repo to ~/.mnema-src
#   3. Creates an isolated Python 3.11 environment with all dependencies
#   4. Installs the `mnema` + `mnema-update` launcher commands
#   5. Runs `mnema --doctor` to verify everything works
#
# Quick start:
#
#   curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh | bash
#
# Or clone first and run locally:
#
#   git clone https://github.com/mienetic/mnema && cd mnema && bash scripts/install.sh
#
# Environment variables you can set to customize the install:
#   MNEMA_REPO          default: https://github.com/mienetic/mnema
#   MNEMA_INSTALL_DIR   default: ~/.mnema-src
#   MNEMA_DATA_DIR      default: ~/.mnema-data
#   MNEMA_BACKEND       default: chroma   (chroma | qdrant | sqlite_vec)
#   MNEMA_EMBEDDING     default: local    (local | openai)
#   MNEMA_EXTRAS        default: default  (comma list: default|all|qdrant|sqlite_vec|openai|...)
#
set -euo pipefail

# --- Config (override via env) -------------------------------------------
MNEMA_REPO="${MNEMA_REPO:-https://github.com/mienetic/mnema}"
MNEMA_INSTALL_DIR="${MNEMA_INSTALL_DIR:-$HOME/.mnema-src}"
MNEMA_DATA_DIR="${MNEMA_DATA_DIR:-$HOME/.mnema-data}"
MNEMA_EMBEDDING="${MNEMA_EMBEDDING:-local}"
MNEMA_EXTRAS="${MNEMA_EXTRAS:-default}"

# Infer the default backend from the chosen extras when the user didn't set
# MNEMA_BACKEND explicitly. This avoids the "installed sqlite_vec but doctor
# complains chroma is missing" trap. Priority: explicit MNEMA_BACKEND > first
# matching backend extra > chroma (the default install).
_infer_backend() {
  case ",$MNEMA_EXTRAS," in
    *,qdrant,*) echo "qdrant" ;;
    *,sqlite_vec,*) echo "sqlite_vec" ;;
    *,chroma,*) echo "chroma" ;;
    *) echo "chroma" ;;  # 'default' and 'all' include chroma
  esac
}
MNEMA_BACKEND="${MNEMA_BACKEND:-$(_infer_backend)}"

# --- Pretty output --------------------------------------------------------
BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { printf "${BLUE}▸${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}!${NC} %s\n" "$*"; }
die()   { printf "${RED}✗${NC} %s\n" "$*" >&2; exit 1; }

cat <<'EOF'
  __  __
 |  \/  | __ _ _ __   __ _  ___  ___
 | |\/| |/ _` | '_ \ / _` |/ _ \/ __|
 | |  | | (_| | | | | (_| |  __/\__ \
 |_|  |_|\__,_|_| |_|\__, |\___||___/
                     |___/   MCP × Vector DB for AI memory
EOF
printf '\n'

# --- Preflight checks -----------------------------------------------------
info "Checking prerequisites..."
command -v git >/dev/null 2>&1 || die "git is required. Install from https://git-scm.com"
ok "git found: $(git --version)"

# Detect OS for the right install commands.
OS="$(uname -s)"
ARCH="$(uname -m)"
info "Detected: $OS on $ARCH"

# --- 1. Install uv (if missing) ------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv (fast Python package manager)..."
  # The official uv installer works on macOS & Linux, x86_64 & arm64.
  if [[ "$OS" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    brew install uv
  else
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv available in this shell.
    export PATH="$HOME/.local/bin:$PATH"
  fi
  command -v uv >/dev/null 2>&1 || die "uv install failed. See https://docs.astral.sh/uv/"
  ok "uv installed: $(uv --version)"
else
  ok "uv already installed: $(uv --version)"
fi

# --- 2. Clone (or update) the repo ---------------------------------------
if [[ -d "$MNEMA_INSTALL_DIR/.git" ]]; then
  info "Existing Mnema source found at $MNEMA_INSTALL_DIR — pulling latest..."
  git -C "$MNEMA_INSTALL_DIR" pull --ff-only
  ok "Source updated."
else
  info "Cloning Mnema to $MNEMA_INSTALL_DIR..."
  rm -rf "$MNEMA_INSTALL_DIR"
  git clone --depth 1 "$MNEMA_REPO" "$MNEMA_INSTALL_DIR"
  ok "Cloned."
fi

PKG_DIR="$MNEMA_INSTALL_DIR/packages/mnema-python"
[[ -f "$PKG_DIR/pyproject.toml" ]] || die "Could not find package at $PKG_DIR"

# Compute the default backend path for the chosen backend. Chroma/Qdrant use a
# directory; sqlite_vec uses a single file (.db). This keeps the launcher and
# doctor consistent with what actually gets installed.
case "$MNEMA_BACKEND" in
  sqlite_vec) _default_backend_path="$MNEMA_DATA_DIR/mnema.db" ;;
  qdrant)     _default_backend_path="$MNEMA_DATA_DIR/qdrant" ;;
  *)          _default_backend_path="$MNEMA_DATA_DIR" ;;  # chroma (dir)
esac

# --- 3. Create the venv & install Mnema ----------------------------------
info "Creating isolated Python 3.11 environment with uv..."
cd "$PKG_DIR"
uv venv --python 3.11 "$MNEMA_INSTALL_DIR/.venv"
# Install with the user's chosen extras (comma-separated). Default = "default"
# which pulls Chroma + local embeddings. Use VIRTUAL_ENV so uv targets our
# venv even when the user hasn't activated it.
VIRTUAL_ENV="$MNEMA_INSTALL_DIR/.venv" uv pip install -e ".[${MNEMA_EXTRAS}]"
ok "Dependencies installed (extras: ${MNEMA_EXTRAS})."

# --- 4. Create launcher scripts ------------------------------------------
info "Installing launcher commands..."
mkdir -p "$HOME/.local/bin"

# Remember the extras used at install time so `mnema-update` preserves them.
echo "$MNEMA_EXTRAS" > "$MNEMA_INSTALL_DIR/.extras"

# mnema → runs the server via the venv's python
cat > "$HOME/.local/bin/mnema" <<EOF
#!/usr/bin/env bash
# Auto-generated by Mnema installer. Runs the Mnema MCP server.
export MNEMA_BACKEND="\${MNEMA_BACKEND:-$MNEMA_BACKEND}"
export MNEMA_BACKEND_PATH="\${MNEMA_BACKEND_PATH:-$_default_backend_path}"
export MNEMA_EMBEDDING="\${MNEMA_EMBEDDING:-$MNEMA_EMBEDDING}"
export MNEMA_DEFAULT_SCOPE="\${MNEMA_DEFAULT_SCOPE:-user:me}"
exec "$MNEMA_INSTALL_DIR/.venv/bin/python" -m mnema "\$@"
EOF
chmod +x "$HOME/.local/bin/mnema"

# mnema-update → pulls latest + reinstalls (preserving the chosen extras)
cat > "$HOME/.local/bin/mnema-update" <<EOF
#!/usr/bin/env bash
# Auto-generated by Mnema installer. Updates Mnema to the latest version.
set -euo pipefail
MNEMA_INSTALL_DIR="$MNEMA_INSTALL_DIR"
PKG_DIR="\$MNEMA_INSTALL_DIR/packages/mnema-python"
EXTRAS="\$(cat "\$MNEMA_INSTALL_DIR/.extras" 2>/dev/null || echo default)"
echo "Updating Mnema from git..."
git -C "\$MNEMA_INSTALL_DIR" pull --ff-only
echo "Reinstalling dependencies (extras: \$EXTRAS)..."
cd "\$PKG_DIR"
VIRTUAL_ENV="\$MNEMA_INSTALL_DIR/.venv" uv pip install -e ".[\$EXTRAS]"
echo "Running doctor check..."
"$HOME/.local/bin/mnema" --doctor
echo "✓ Mnema updated."
EOF
chmod +x "$HOME/.local/bin/mnema-update"

# --- 5. Ensure ~/.local/bin is on PATH -----------------------------------
ensure_path() {
  local shell_rc="$1"
  local marker='# Added by Mnema installer'
  local path_line='export PATH="$HOME/.local/bin:$PATH"'
  if [[ -f "$shell_rc" ]] && ! grep -qF "$marker" "$shell_rc"; then
    printf '\n%s\n%s\n' "$marker" "$path_line" >> "$shell_rc"
    warn "Added ~/.local/bin to PATH in $shell_rc — open a new terminal or run: source $shell_rc"
  fi
}
case "${SHELL:-}" in
  */zsh)  ensure_path "$HOME/.zshrc" ;;
  */bash) ensure_path "$HOME/.bashrc" ;;
esac
# Even if we couldn't detect the shell, try the home bin dir now.
export PATH="$HOME/.local/bin:$PATH"

# --- 6. Verify -----------------------------------------------------------
info "Running doctor check (first run will download the embedding model)..."
if "$HOME/.local/bin/mnema" --doctor; then
  printf '\n'
  ok "Mnema is installed and ready!"
else
  die "Doctor check failed. See the messages above."
fi

# --- 7. Print next steps -------------------------------------------------
mkdir -p "$MNEMA_DATA_DIR"
cat <<EOF

${BOLD}Next steps${NC}

  1. Test it now:
       ${BOLD}mnema --doctor${NC}

  2. Run the MCP server (for CLI testing):
       ${BOLD}mnema${NC}

  3. Add Mnema to your AI client. Pick the right config file:
       ${BLUE}Claude Desktop${NC} → copy ~/.mnema-src/examples/claude-desktop-config.json
       ${BLUE}ZCode${NC}            → copy ~/.mnema-src/examples/zcode-mcp-config.json
       ${BLUE}Cursor${NC}           → copy ~/.mnema-src/examples/cursor-mcp-config.json

  4. Update later (pulls latest from GitHub + reinstalls):
       ${BOLD}mnema-update${NC}

  5. Customize behavior via env vars (MNEMA_BACKEND, MNEMA_EMBEDDING, ...):
       ${BLUE}https://github.com/mienetic/mnema#configuration${NC}

${BOLD}Files installed${NC}
  Source:     $MNEMA_INSTALL_DIR
  Data:       $MNEMA_DATA_DIR
  Launcher:   ~/.local/bin/mnema
  Updater:    ~/.local/bin/mnema-update

EOF
