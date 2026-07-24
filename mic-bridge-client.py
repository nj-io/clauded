#!/usr/bin/env python3
"""
On-demand mic bridge client — runs inside the clauded container.

Watches the container-local PulseAudio 'micbridge' pipe-source. While Claude
Code is actually recording (source State: RUNNING), it opens an authenticated
connection to the Mac mic-server and pumps microphone PCM into the pipe-source's
FIFO. The moment recording stops, it disconnects — so the Mac mic is live only
while you're dictating (and the macOS mic indicator reflects exactly that).

Env (injected by clauded):
  CLAUDED_MIC_HOST, CLAUDED_MIC_PORT, CLAUDED_BRIDGE_TOKEN,
  CLAUDED_SESSION_NAME, CLAUDED_MIC_FIFO
"""

import os
import socket
import subprocess
import time

HOST = os.environ.get("CLAUDED_MIC_HOST", "host.docker.internal")
PORT = int(os.environ.get("CLAUDED_MIC_PORT", "21566"))
TOKEN = os.environ.get("CLAUDED_BRIDGE_TOKEN", "")
SESSION = os.environ.get("CLAUDED_SESSION_NAME", "clauded")
FIFO = os.environ.get("CLAUDED_MIC_FIFO", "/tmp/clauded-mic.fifo")
SOURCE = "micbridge"
CHUNK = 3200


def source_running():
    """True when a client (Claude Code's SoX) is actively recording the source.

    Uses `pactl list sources short` — one tab-separated line per source
    (idx, name, module, spec, state), so name and state are unambiguous
    (the long format lists State before Name, which is easy to misparse).
    """
    try:
        out = subprocess.run(["pactl", "list", "sources", "short"],
                             capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return False
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 5 and parts[1] == SOURCE and parts[-1].strip() == "RUNNING":
            return True
    return False


def stream_once():
    """Connect + authenticate, then pump mic PCM into the FIFO until recording
    stops or the peer closes."""
    sock = socket.create_connection((HOST, PORT), timeout=5)
    fd = None
    try:
        sock.sendall((TOKEN + "\t" + SESSION + "\n").encode())
        fd = os.open(FIFO, os.O_WRONLY)  # PA holds the read end open
        sock.settimeout(1)
        last_check = 0.0
        while True:
            now = time.monotonic()
            if now - last_check > 0.3:
                if not source_running():
                    break
                last_check = now
            try:
                data = sock.recv(CHUNK)
            except socket.timeout:
                continue
            if not data:
                break
            os.write(fd, data)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        sock.close()


def main():
    if not TOKEN:
        return
    while True:
        try:
            if source_running():
                stream_once()
            else:
                time.sleep(0.2)
        except Exception:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
