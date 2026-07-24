#!/usr/bin/env python3
"""
Mic bridge — runs on your Mac. On an authenticated + consented connection it
captures the default microphone with SoX and streams raw PCM (16 kHz mono
s16le) to a clauded container, ONLY while the connection is open. Nothing is
written to disk.

Security model (the container and a prompt-injected agent share one trust
domain, so consent has to live here, on the host, where the agent can't reach):

  1. Token       — every connection must present the per-machine secret from
                   ~/.clauded/bridge-token. No token file => refuse everything.
  2. Consent     — the FIRST recording of a session pops a native macOS dialog
                   naming the session; denied by default, times out to denied.
                   Approval is cached per session for CONSENT_TTL. Set
                   CLAUDED_MIC_CONSENT=always to prompt before every recording.
  3. On-demand   — SoX (and the mic) run only for the life of a connection, so
                   the mic is live only while you're actually dictating. macOS
                   shows its orange mic indicator the whole time.
  4. Duration cap— a single capture is force-stopped after MAX_CAPTURE seconds.
  5. Audit       — every capture is logged to ~/.clauded/mic.log.

Protocol (raw TCP): client sends "<token>\t<session>\n", then the server streams
raw PCM until the client disconnects.
"""

import socket
import subprocess
import os
import sys
import time
import secrets
import threading

PORT = int(os.environ.get("CLAUDE_MIC_PORT", 21566))
TOKEN_FILE = os.path.expanduser("~/.clauded/bridge-token")
LOG_FILE = os.path.expanduser("~/.clauded/mic.log")
CONSENT_MODE = os.environ.get("CLAUDED_MIC_CONSENT", "session")  # session | always
CONSENT_TTL = int(os.environ.get("CLAUDED_MIC_CONSENT_TTL", 3600))  # seconds
MAX_CAPTURE = int(os.environ.get("CLAUDED_MIC_MAX_CAPTURE", 900))   # seconds
DIALOG_TIMEOUT = 20  # seconds the consent dialog waits before denying

SOX_CMD = ["sox", "-q", "-d", "-t", "raw", "-e", "signed", "-b", "16",
           "-c", "1", "-r", "16000", "-"]
CHUNK = 3200  # ~100 ms at 16 kHz mono s16le

_consent_lock = threading.Lock()
_consent_cache = {}  # session -> epoch granted


def _load_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


TOKEN = _load_token()


def _log(session, event, **extra):
    parts = [time.strftime("%Y-%m-%dT%H:%M:%S"), f"session={session}", f"event={event}"]
    parts += [f"{k}={v}" for k, v in extra.items()]
    try:
        with open(LOG_FILE, "a") as f:
            f.write(" ".join(parts) + "\n")
    except OSError:
        pass


def _ask_consent(session):
    """Native macOS dialog. Returns True only on an explicit Allow click."""
    safe = session.replace('"', "").replace("\\", "")[:60]
    script = (
        f'display dialog "clauded session \\"{safe}\\" wants to use your microphone '
        f'for voice input." with title "clauded voice" '
        f'buttons {{"Deny", "Allow"}} default button "Deny" '
        f'giving up after {DIALOG_TIMEOUT}'
    )
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True,
                           text=True, timeout=DIALOG_TIMEOUT + 5)
        return "button returned:Allow" in r.stdout
    except Exception:
        return False


def _consented(session):
    if CONSENT_MODE == "always":
        return _ask_consent(session)
    with _consent_lock:
        granted = _consent_cache.get(session, 0)
        if time.time() - granted < CONSENT_TTL:
            return True
    ok = _ask_consent(session)
    if ok:
        with _consent_lock:
            _consent_cache[session] = time.time()
    return ok


def _read_header(conn):
    conn.settimeout(5)
    buf = b""
    while b"\n" not in buf and len(buf) < 512:
        chunk = conn.recv(64)
        if not chunk:
            return None, None
        buf += chunk
    conn.settimeout(None)
    line = buf.split(b"\n", 1)[0].decode(errors="replace")
    token, _, session = line.partition("\t")
    return token.strip(), (session.strip() or "clauded")


def handle(conn):
    try:
        token, session = _read_header(conn)
        if not TOKEN or token is None or not secrets.compare_digest(token, TOKEN):
            return  # unauthorized — mic never opens
        if not _consented(session):
            _log(session, "denied")
            return
        started = time.time()
        _log(session, "start")
        proc = subprocess.Popen(SOX_CMD, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                if time.time() - started > MAX_CAPTURE:
                    break
                data = proc.stdout.read(CHUNK)
                if not data:
                    break
                conn.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            _log(session, "stop", duration=f"{time.time() - started:.1f}s")
    finally:
        conn.close()


def main():
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(4)
    print(f"Mic bridge listening on {port} (consent={CONSENT_MODE})")
    if not TOKEN:
        print("Warning: no ~/.clauded/bridge-token — refusing all connections.")
    try:
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=handle, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
