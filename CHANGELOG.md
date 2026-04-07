# Changelog

## 2026-04-03

1. **Clipboard support.** Claude Code's `/copy` command now copies to your Mac's native clipboard. Works via an HTTP clipboard server (`clipboard-server.py`, port 21564) on the Mac, with `xclip` and `xsel` shims inside the container. Also includes `pbcopy`/`pbpaste` shims as fallbacks. Auto-starts in `ensure_ready()` with a `clauded clipboard start|stop|install|status` subcommand.

2. **URL opening.** Links clicked inside clauded now open in your Mac browser. An `xdg-open` shim in the container forwards URLs to the clipboard server's `/open` endpoint, which calls `open` on the Mac.

3. **MCP server support (xactions, context7, playwright).** Stdio MCP servers now run inside Docker. Installed system Chromium with Puppeteer/Playwright env vars so browser-based MCPs work on ARM64 Linux. The xactions source directory is mounted read-only from `~/.local/share/xactions`. Context7 works out of the box (HTTP remote). Playwright should work with the system Chromium (untested).

4. **.claude.json sync (copy-in, sync-back).** Replaced the fragile file bind mount of `~/.claude.json` with a copy-based approach. The host's config is copied into the Docker persistent home before each launch, and synced back after exit. This avoids Claude Code's atomic writes breaking the bind mount mid-session. Also cleans up stale `.mcp.json` from the persistent home on each launch.

5. **Docker image version cache busting.** `cmd_build()` now passes the latest Claude Code version as a `CLAUDE_VERSION` build arg. Docker reuses the cached layer if the version hasn't changed, and re-downloads only when a new version is available.

6. **Duplicate home mount fix.** Running `clauded` from `~` no longer fails with "Duplicate mount point." Added a check to skip the auto-mount when the resolved path is `$HOME`.

7. **Firewall: Chrome bridge whitelist.** Added `bridge.claudeusercontent.com` to `init-firewall.sh` for future Chrome integration support. Only applies when the firewall is explicitly activated.

## 2026-04-05

8. **Chrome MCP bridge.** Added `chrome-mcp-bridge.py` (port 21565) which runs `claude --claude-in-chrome-mcp` as a persistent subprocess on the Mac and exposes it over HTTP to Docker. The bridge handles the MCP initialize handshake internally and translates between HTTP and stdio. Auto-starts in `ensure_ready()` with a `clauded chrome-mcp start|stop|restart|status` subcommand. The Chrome MCP config is automatically injected into the Docker copy of `.claude.json` when the bridge is running, so `claude-in-chrome` tools appear in clauded sessions without manual config.

9. **xactions mount read-write.** Changed the xactions source mount from read-only to read-write so clauded sessions can edit xactions code directly.

10. **.claude.json symlink migration.** Replaced the fragile copy-in/sync-back approach with a one-time automated symlink. On first run, `clauded` moves `~/.claude.json` into `~/.claude/.claude.json` and creates a symlink. Since `~/.claude/` is directory-mounted (not file-mounted), Claude Code's atomic writes work correctly. Both native Claude and Docker sessions read/write the same file. The symlink is also mirrored in the Docker persistent home so it resolves inside containers.

11. **Memory usage warning.** `ensure_ready()` now checks total memory usage of running clauded containers. If it exceeds 3GB, it shows a warning listing the running sessions and suggests stopping idle ones. Non-blocking — just a heads up before launching.

12. **Parallel session hang fix.** Fixed second `clauded` session hanging when launched while another is running. Root cause: `ln -sf` on the persistent home's `.claude.json` symlink was deleting and recreating it, which triggered Claude Code v83+'s file watchers (chokidar) in the first container and left shared state in a broken condition. Fix: only create the symlink if it doesn't already exist.

13. **Docker image cleanup.** `cmd_build()` now runs `docker image prune` and `docker builder prune` after each build to clean up old dangling images and build cache.

14. **Resume startup speed fix.** `clauded --resume` was taking 20+ seconds because it ran two `find` commands scanning the entire `~/dev` tree to locate the session's working directory. Replaced with reading the `cwd` directly from the session's JSONL file — now takes 0.1 seconds.

15. **Session tracking fix.** Resume hints now parse the session ID from Claude Code's own terminal output (via `script` capture) instead of guessing from the most recently modified JSONL. Fixes wrong session being shown when multiple sessions share the same workdir.

16. **Generalized configuration.** Removed hardcoded paths and made clauded usable by others. Added `~/.claude-docker/config` for user-specific settings: project directory (`DEV_DIR`), extra mounts (`EXTRA_MOUNTS`), optional SSH/git config overrides. SSH keys now mount the entire `~/.ssh` directory. Dockerfile uses build args for UID/GID/HOME instead of hardcoded values. Entrypoint checks common conda paths instead of one hardcoded path.

17. **`-r` shorthand for `--resume`.** Added `-r` as an alias for `--resume`, matching native Claude Code's CLI.

18. **Branch container naming.** When resuming a session whose container is already running (e.g. after `/branch`), clauded appends a random suffix to the container name instead of conflicting. Stale stopped containers with the same name are also cleaned up automatically.

19. **Resume workdir fix.** When resuming a session created in a worktree, clauded now derives the workdir from the JSONL file's project directory path instead of the embedded cwd. Fixes "No conversation found" errors for worktree sessions.

## 2026-04-07

20. **Open source preparation.** Removed all hardcoded user-specific paths. Added config.example, ssh-config-docker.example, gitconfig-docker.example. Added LICENSE (MIT), README.md, .gitignore. Dockerfile uses generic defaults with build args. Plist files generated dynamically. Auto-creates ~/.claude-docker/config from template on first run.

21. **One-liner installer.** Added `install.sh` for `curl | bash` installation. Clones repo, builds image, symlinks to PATH.

22. **Container name sanitization.** Session names with spaces or special characters are now sanitized to Docker-safe characters, fixing "Invalid container name" errors when resuming sessions with long names.
