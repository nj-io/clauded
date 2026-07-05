#!/usr/bin/env python3
"""
Tiny HTTP host-services server — runs on your Mac, provides clipboard and URL opening
for Docker containers.

Start:  python3 clipboard-server.py
        python3 clipboard-server.py --port 21564

Requests must carry the shared secret from ~/.clauded/bridge-token in an
X-Clauded-Token header (clauded injects it into containers). This stops anything
else that can reach the port — other devices on your LAN, a Tailnet — from
reading your clipboard or opening URLs on your Mac. GET /health needs no token.

Usage from container:
        echo "hello" | curl -X POST -H "X-Clauded-Token: $CLAUDED_BRIDGE_TOKEN" -d @- http://host.docker.internal:21564/copy
        curl -H "X-Clauded-Token: $CLAUDED_BRIDGE_TOKEN" http://host.docker.internal:21564/paste
        curl -X POST -H "X-Clauded-Token: $CLAUDED_BRIDGE_TOKEN" -d "https://example.com" http://host.docker.internal:21564/open
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import subprocess
import secrets
import os
import sys

PORT = int(os.environ.get("CLAUDE_CLIPBOARD_PORT", 21564))

TOKEN_FILE = os.path.expanduser("~/.clauded/bridge-token")


def _load_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


TOKEN = _load_token()


class ClipboardHandler(BaseHTTPRequestHandler):
    def _authed(self):
        if not TOKEN:
            return True  # no token configured yet — clauded creates it on first run
        return secrets.compare_digest(self.headers.get("X-Clauded-Token", ""), TOKEN)

    def do_POST(self):
        if not self._authed():
            self.send_response(403)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        path = urlparse(self.path).path

        if path == "/open":
            # Open a URL in the default Mac browser
            url = body.decode("utf-8", errors="replace").strip()
            try:
                subprocess.Popen(
                    ["open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.send_response(200)
            except Exception:
                self.send_response(500)
        else:
            # Default: copy to clipboard
            try:
                proc = subprocess.run(
                    ["pbcopy"],
                    input=body,
                    timeout=5,
                )
                self.send_response(200 if proc.returncode == 0 else 500)
            except Exception:
                self.send_response(500)

        self.end_headers()

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self.send_response(200)
            self.end_headers()
            return
        if not self._authed():
            self.send_response(403)
            self.end_headers()
            return
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                timeout=5,
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(result.stdout)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silent


def main():
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    server = HTTPServer(("0.0.0.0", port), ClipboardHandler)
    print(f"Clipboard server listening on port {port}")
    if not TOKEN:
        print("Warning: no ~/.clauded/bridge-token found — running without auth.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
