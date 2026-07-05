#!/usr/bin/env python3
"""
Tiny HTTP sound server — runs on your Mac, plays sounds when Docker containers ask.

Start:  python3 sound-server.py
        python3 sound-server.py --port 21563

Requests must carry the shared secret from ~/.clauded/bridge-token in an
X-Clauded-Token header (clauded injects it into containers). GET /health needs none.

Usage from container:
        curl -H "X-Clauded-Token: $CLAUDED_BRIDGE_TOKEN" http://host.docker.internal:21563/?sound=Submarine
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import subprocess
import secrets
import os
import sys

PORT = int(os.environ.get("CLAUDE_SOUND_PORT", 21563))

SOUNDS_DIR = "/System/Library/Sounds"

TOKEN_FILE = os.path.expanduser("~/.clauded/bridge-token")


def _load_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


TOKEN = _load_token()


class SoundHandler(BaseHTTPRequestHandler):
    def _authed(self):
        if not TOKEN:
            return True  # no token configured yet — clauded creates it on first run
        return secrets.compare_digest(self.headers.get("X-Clauded-Token", ""), TOKEN)

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self.send_response(200)
            self.end_headers()
            return
        if not self._authed():
            self.send_response(403)
            self.end_headers()
            return

        params = parse_qs(urlparse(self.path).query)
        sound = params.get("sound", ["Submarine"])[0]

        # Sanitize: only allow alphanumeric sound names
        sound = "".join(c for c in sound if c.isalnum())
        sound_file = os.path.join(SOUNDS_DIR, f"{sound}.aiff")

        if os.path.exists(sound_file):
            subprocess.Popen(
                ["afplay", sound_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.send_response(200)
        else:
            self.send_response(404)

        self.end_headers()

    do_POST = do_GET

    def log_message(self, format, *args):
        pass  # Silent


def main():
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    server = HTTPServer(("0.0.0.0", port), SoundHandler)
    print(f"Sound server listening on port {port}")
    if not TOKEN:
        print("Warning: no ~/.clauded/bridge-token found — running without auth.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
