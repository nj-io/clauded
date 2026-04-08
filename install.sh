#!/bin/bash
# clauded installer — run with:
#   curl -fsSL https://raw.githubusercontent.com/nj-io/clauded/main/install.sh | bash

set -eo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[0;33m'; NC='\033[0m'
log() { echo -e "${BLUE}[clauded]${NC} $*"; }
ok()  { echo -e "${GREEN}[clauded]${NC} $*"; }
err() { echo -e "${RED}[clauded]${NC} $*" >&2; }

INSTALL_DIR="${CLAUDED_DIR:-$HOME/.clauded}"
BIN_DIR="/usr/local/bin"

# Check prerequisites
if ! command -v docker &>/dev/null; then
    err "Docker not found. Install Docker Desktop first: https://docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &>/dev/null; then
    err "Docker Desktop is not running. Start it and try again."
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

# Symlink clauded and play-sound to PATH
log "Adding to PATH..."
if [[ -w "$BIN_DIR" ]]; then
    ln -sf "$INSTALL_DIR/clauded" "$BIN_DIR/clauded"
    ln -sf "$INSTALL_DIR/play-sound" "$BIN_DIR/play-sound"
else
    sudo ln -sf "$INSTALL_DIR/clauded" "$BIN_DIR/clauded"
    sudo ln -sf "$INSTALL_DIR/play-sound" "$BIN_DIR/play-sound"
fi

# Start host services
log "Starting host services..."
./clauded sounds start
./clauded clipboard start

echo ""
ok "Installed successfully."
echo ""
echo "  Run:              clauded"
echo "  Resume session:   clauded -r <name-or-id>"
echo "  Update:           clauded build"
echo "  Help:             clauded help"
echo ""
echo -e "  ${YELLOW}Optional:${NC} Auto-start services on login:"
echo "    clauded sounds install"
echo "    clauded clipboard install"
echo ""
