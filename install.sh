#!/bin/bash
# clauded installer — run with:
#   curl -fsSL https://raw.githubusercontent.com/nj-io/clauded/main/install.sh | bash

set -eo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${BLUE}[clauded]${NC} $*"; }
ok()  { echo -e "${GREEN}[clauded]${NC} $*"; }
err() { echo -e "${RED}[clauded]${NC} $*" >&2; }

INSTALL_DIR="${CLAUDED_DIR:-$HOME/.clauded}"
BIN_LINK="/usr/local/bin/clauded"

# Check prerequisites
if ! command -v docker &>/dev/null; then
    err "Docker not found. Install Docker Desktop first: https://docker.com/products/docker-desktop"
    exit 1
fi

if ! command -v git &>/dev/null; then
    err "git not found."
    exit 1
fi

# Clone or update
if [[ -d "$INSTALL_DIR" ]]; then
    log "Updating existing installation..."
    cd "$INSTALL_DIR" && git pull --ff-only
else
    log "Installing to $INSTALL_DIR..."
    git clone https://github.com/nj-io/clauded.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Build the Docker image
log "Building Docker image (this takes a few minutes on first install)..."
./clauded build

# Symlink to PATH
if [[ -w "$(dirname "$BIN_LINK")" ]]; then
    ln -sf "$INSTALL_DIR/clauded" "$BIN_LINK"
else
    log "Adding clauded to PATH (requires sudo)..."
    sudo ln -sf "$INSTALL_DIR/clauded" "$BIN_LINK"
fi

echo ""
ok "Installed successfully."
echo ""
echo "  Run:     clauded"
echo "  Update:  clauded build"
echo "  Help:    clauded help"
echo ""
