#!/usr/bin/env python3
"""
Tiny HTTP sound server — runs on your Mac, plays sounds when Docker containers ask.

Start:  python3 sound-server.py
        python3 sound-server.py --port 21563

Usage from container:
        curl http://host.docker.internal:21563/?sound=Submarine
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import subprocess
import os
import sys

PORT = int(os.environ.get("CLAUDE_SOUND_PORT", 21563))

SOUNDS_DIR = "/System/Library/Sounds"


class SoundHandler(BaseHTTPRequestHandler):
    def do_GET(self):
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
    print(f"Test: curl http://localhost:{port}/?sound=Submarine")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
