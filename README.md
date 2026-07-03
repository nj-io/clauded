<p align="center">
  <img src="assets/banner.png" alt="clauded — Claude Code in Docker" width="100%">
</p>

<p align="center">
  <strong>Run Claude Code in Docker with full feature parity.</strong><br>
  Sandboxed sessions with clipboard, browser control, MCP servers, parallel sessions, and sound notifications — all bridged seamlessly to your Mac.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#usage">Usage</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

## Why

Claude Code runs with full filesystem access. Docker gives you sandboxed sessions without sacrificing the features you rely on: clipboard, browser links, git, MCP servers, and sound notifications all bridge to your Mac transparently.

## Features

- **Parallel sessions** — run as many sessions as you want across different projects, simultaneously
- **Resume by name or ID** — session names are tracked automatically, `clauded -r my-session` picks up where you left off
- **Clipboard bridge** — `/copy` and copy-on-select both copy to your Mac's clipboard
- **URL opening** — links clicked inside Docker open in your Mac browser
- **Sound notifications** — hear when Claude finishes a task
- **Chrome browser control** — navigate, click, screenshot, and read the console in your Mac's Chrome, built in — no flag needed
- **MCP server support** — stdio and HTTP MCPs work inside Docker, with Chromium pre-installed for Puppeteer/Playwright
- **Auto host networking** — when Docker Desktop host networking is enabled, all container ports are automatically accessible on your Mac without `--port`
- **Auto-update** — checks for new Claude Code versions on startup and rebuilds the image when one is available (skip with `--no-update`)
- **Git and SSH** — all SSH keys mounted, GitHub auth forwarded via `GH_TOKEN`
- **Per-session isolation** — each session gets its own `/tmp`, container name, and resume log
- **Memory warnings** — alerts when running containers exceed 3GB total
- **Image cleanup** — old Docker images and build cache pruned automatically after each build
- **Configurable** — project directory, extra mounts, SSH/git overrides all in `~/.clauded/config`

## Prerequisites

- macOS (Apple Silicon or Intel)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (must be running)
- A Claude account (Pro, Max, Teams, or Enterprise)

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/nj-io/clauded/main/install.sh | bash
```

This clones the repo, builds the Docker image, symlinks `clauded` and `play-sound` to your PATH, and starts the clipboard/sound host services.

<details>
<summary>Manual installation</summary>

```bash
git clone https://github.com/nj-io/clauded.git ~/.clauded
cd ~/.clauded && ./clauded build
sudo ln -sf ~/.clauded/clauded /usr/local/bin/clauded
sudo ln -sf ~/.clauded/play-sound /usr/local/bin/play-sound
```

</details>

On first run, clauded will:
1. Build the Docker image with Chromium, Node.js, Python, and Claude Code
2. Start the clipboard and sound servers on your Mac
3. Migrate `~/.claude.json` into `~/.claude/` (one-time symlink for Docker compatibility)
4. Open a login URL in your browser — authenticate with your Claude account

Optional: auto-start host services on login so they're always ready:

```bash
clauded sounds install
clauded clipboard install
```

## Usage

### Sessions

```bash
clauded                                    # Start in current directory
clauded ~/dev/my-project                   # Start in a specific directory
clauded -r <id-or-name>                    # Resume a session
clauded --continue                         # Resume last session
clauded --fork-session <id-or-name>        # Resume a copy, leaving the original untouched
clauded --worktree                         # Start in a git worktree
clauded --worktree my-feature              # Named worktree
clauded --no-update                        # Start without checking for updates
clauded --version 2.1.150                  # Pin to a specific Claude Code version
```

### Chrome Browser Control

Claude in Chrome works out of the box. Install the [Claude in Chrome extension](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) and Claude can navigate, click, screenshot, and read the console in your Mac's Chrome from inside the container — no flag or setup required. The `mcp__claude-in-chrome__*` tools are available automatically.

### Ports & Mounts

```bash
clauded --port 4000                        # Expose port 4000 to Mac
clauded --port 4000-4010                   # Expose port range
clauded --ro ~/specs                       # Mount extra directory read-only
clauded --mount ~/data:/data               # Mount extra directory read-write
```

### Agents

```bash
clauded --agent my-agent "prompt"          # Run a Claude agent
clauded run "prompt"                       # Non-interactive query
```

### Session Management

```bash
clauded list                               # See running sessions
clauded stop                               # Stop most recent session
clauded stop-all                           # Stop all sessions
clauded shell                              # Bash into most recent session
```

### Services

```bash
clauded sounds start|stop|status|install|uninstall     # Sound notifications (port 21563)
clauded clipboard start|stop|status|install|uninstall  # Clipboard bridge (port 21564)
```

### Build & Maintenance

```bash
clauded build                              # Build/rebuild (auto-detects updates)
clauded firewall                           # Lock down outbound network access
clauded setup                              # Full setup wizard
```

## Configuration

User settings live in `~/.clauded/config` (auto-created on first run):

```bash
# Project directory mounted into containers
DEV_DIR="$HOME/dev"

# Extra directories to mount read-write (space-separated)
EXTRA_MOUNTS="$HOME/.my-tool $HOME/.local/share/my-mcp"

# Custom SSH config for Docker (leave empty to use ~/.ssh/config)
SSH_CONFIG="$SCRIPT_DIR/ssh-config-docker"

# Custom gitconfig for Docker (leave empty to use ~/.gitconfig)
GITCONFIG="$SCRIPT_DIR/gitconfig-docker"

# Skip the auto-update check on startup (same as --no-update)
# SKIP_UPDATE="true"

# Pin Claude Code to a specific version (same as --version)
# CLAUDE_PIN_VERSION="2.1.150"

# Force Anthropic endpoints to IPv4 under host networking (auto | true | false)
# FORCE_IPV4="auto"
```

### SSH & Git

All SSH keys from `~/.ssh/` are mounted read-only. If your `~/.ssh/config` or `~/.gitconfig` have Mac-specific entries (Keychain credential helpers, etc.), create Docker-specific overrides:

```bash
cp ssh-config-docker.example ssh-config-docker   # Edit with your key
cp gitconfig-docker.example gitconfig-docker       # Edit with your email
```

### MCP Servers

MCP servers configured in `~/.claude.json` work automatically if their dependencies are available in the container. The image includes:

| Dependency | For |
|---|---|
| Chromium (headless) | Puppeteer and Playwright MCPs |
| Node.js 22 + npm | JavaScript-based MCPs |
| Python 3 | Python-based MCPs |

**HTTP/SSE MCPs** (Asana, GitHub, Linear, Slack, Supabase, etc.) work out of the box.

**Claude in Chrome** is built in and needs no bridge — just install the extension (see [Chrome Browser Control](#chrome-browser-control)).

To mount additional MCP source directories, add them to `EXTRA_MOUNTS` in your config.

## How It Works

clauded runs Claude Code inside Docker while bridging Mac features via lightweight HTTP servers on the host:

<p align="center">
  <img src="assets/architecture.png" alt="clauded architecture" width="90%">
</p>

Sessions share `~/.claude/` via bind mount. Each container gets isolated `/tmp`. The persistent Docker home at `~/.clauded/home` survives container restarts.

## Parallel Sessions

Multiple sessions run simultaneously with isolated containers but shared project files and Claude settings:

```bash
# Terminal 1                    # Terminal 2                    # Terminal 3
clauded ~/dev/backend           clauded ~/dev/frontend          clauded -r my-session
```

A memory warning appears when total container usage exceeds 3GB.

## Network Firewall

Optionally restrict outbound traffic to only essential services:

```bash
clauded firewall
```

Whitelisted: Anthropic API, GitHub, npm, PyPI, Claude-in-Chrome relay.

## Troubleshooting

### VPNs that don't route IPv6

Some VPNs advertise IPv6 but can't route it. With host networking enabled, that breaks the container's connection to Anthropic — you'd see `401 Invalid authentication credentials` or a certificate error.

clauded handles this automatically: it checks whether Anthropic is reachable over IPv6 and pins the endpoints to IPv4 only if it isn't.

To override the auto-detection:

```bash
clauded --force-ipv4      # always pin to IPv4
clauded --no-force-ipv4   # never pin
```

Or set it permanently in `~/.clauded/config`:

```bash
FORCE_IPV4="auto"    # auto (default) | true (always pin) | false (never)
```

## Contributing

Found a bug or have a feature request? [Open an issue](https://github.com/nj-io/clauded/issues).

Pull requests welcome. For larger changes, open an issue first to discuss.

## License

[MIT](LICENSE)
