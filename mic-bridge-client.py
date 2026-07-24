#!/usr/bin/env python3
"""
On-demand mic bridge client — runs inside the clauded container.

Watches the container-local PulseAudio 'micbridge' pipe-source. While Claude
Code is recording (source State: RUNNING), it opens an authenticated connection
to the Mac mic-server and pumps microphone PCM into the pipe-source's FIFO;
shortly after recording stops it disconnects (poll granularity is sub-second),
so the Mac mic runs while you're recording rather than for the whole session.

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
FIFO = os.environ.get("CLAUDED_MIC_FIFO", "/dev/shm/clauded-mic.fifo")
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


MIN_RETRY = 0.5


def main():
    if not TOKEN:
        return
    backoff = MIN_RETRY
    while True:
        if not source_running():
            backoff = MIN_RETRY
            time.sleep(0.5)  # idle poll; ~0.5s to start streaming once recording begins
            continue
        start = time.monotonic()
        try:
            stream_once()
        except Exception:
            pass
        # If the attempt ended almost immediately (server refused — e.g. a
        # denied/cooled-down consent, or sox missing on the Mac), back off so
        # we neither hammer the server nor spin the CPU. A real stream resets it.
        if time.monotonic() - start < 0.5:
            time.sleep(backoff)
            backoff = min(backoff * 2, 5.0)
        else:
            backoff = MIN_RETRY


if __name__ == "__main__":
    main()
