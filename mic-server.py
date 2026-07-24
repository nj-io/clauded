#!/usr/bin/env python3
"""
Mic bridge — runs on your Mac. On an authenticated + approved connection it
captures the default microphone with SoX and streams raw PCM (16 kHz mono
s16le) to a clauded container while the connection is open. Nothing is written
to disk.

How access works:
  - Token: every connection must present the per-machine secret from
    ~/.clauded/bridge-token (the same token clauded injects into containers),
    so other devices on your network can't use it.
  - Approval: the first recording of a session opens a macOS dialog naming the
    session. It's denied by default and times out to denied. An approval is
    cached for the session; a denial is remembered briefly so a client that
    keeps retrying can't turn it into a prompt loop. Set
    CLAUDED_MIC_CONSENT=always to be asked before every recording.
  - macOS shows its microphone indicator whenever a capture is running, and
    every capture is recorded in ~/.clauded/mic.log.

Protocol (raw TCP): client sends "<token>\t<session>\n", then the server streams
raw PCM until the client disconnects.
"""

import socket
import subprocess
import shutil
import os
import sys
import time
import secrets
import threading

PORT = int(os.environ.get("CLAUDE_MIC_PORT", 21566))
TOKEN_FILE = os.path.expanduser("~/.clauded/bridge-token")
LOG_FILE = os.path.expanduser("~/.clauded/mic.log")
CONSENT_MODE = os.environ.get("CLAUDED_MIC_CONSENT", "session")  # session | always
CONSENT_TTL = int(os.environ.get("CLAUDED_MIC_CONSENT_TTL", 3600))
DENY_COOLDOWN = int(os.environ.get("CLAUDED_MIC_DENY_COOLDOWN", 60))
MAX_CAPTURE = int(os.environ.get("CLAUDED_MIC_MAX_CAPTURE", 900))
MAX_CONNECTIONS = 8
DIALOG_TIMEOUT = 20  # seconds the consent dialog waits before denying

SOX_CMD = ["sox", "-q", "-d", "-t", "raw", "-e", "signed", "-b", "16",
           "-c", "1", "-r", "16000", "-"]
CHUNK = 3200  # ~100 ms at 16 kHz mono s16le

_lock = threading.Lock()
_allow = {}   # session -> approval epoch
_deny = {}    # session -> deny-until epoch
_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)


def _load_token():
    try:
        with open(TOKEN_FILE, "rb") as f:
            return f.read().strip()
    except OSError:
        return None


TOKEN = _load_token()  # bytes


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
    safe = "".join(c for c in session if c.isprintable()).replace('"', "").replace("\\", "")[:60]
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
    now = time.time()
    with _lock:
        if now < _deny.get(session, 0):
            return False  # recently denied — refuse quietly instead of re-prompting
        if CONSENT_MODE != "always" and now - _allow.get(session, 0) < CONSENT_TTL:
            return True
    ok = _ask_consent(session)
    with _lock:
        if ok:
            _allow[session] = time.time()
        else:
            _deny[session] = time.time() + DENY_COOLDOWN
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
    token, _, session = buf.split(b"\n", 1)[0].partition(b"\t")
    # Sanitize the session label once (it goes into the dialog and the log):
    # printable, no whitespace, bounded length.
    sess = session.strip().decode("utf-8", "replace")
    sess = "".join(c for c in sess if c.isprintable() and not c.isspace())[:64] or "clauded"
    return token.strip(), sess


def handle(conn):
    try:
        token, session = _read_header(conn)
        if not TOKEN or token is None or not secrets.compare_digest(token, TOKEN):
            return
        if not _consented(session):
            _log(session, "denied")
            return
        if shutil.which("sox") is None:
            _log(session, "error", detail="sox-not-found")
            return
        try:
            proc = subprocess.Popen(SOX_CMD, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as e:
            _log(session, "error", detail=f"sox-spawn-failed:{e.errno}")
            return
        started = time.time()
        _log(session, "start")
        try:
            while time.time() - started <= MAX_CAPTURE:
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


def _serve(conn):
    try:
        handle(conn)
    finally:
        _slots.release()


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
            if not _slots.acquire(blocking=False):
                conn.close()  # too many concurrent connections
                continue
            threading.Thread(target=_serve, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
