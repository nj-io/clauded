#!/usr/bin/env python3
"""
Tiny HTTP host-services server — runs on your Mac, provides clipboard and URL opening
for Docker containers.

Start:  python3 clipboard-server.py
        python3 clipboard-server.py --port 21564

Usage from container:
        echo "hello" | curl -X POST -d @- http://host.docker.internal:21564/copy
        curl http://host.docker.internal:21564/paste
        curl -X POST -d "https://example.com" http://host.docker.internal:21564/open
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import subprocess
import shlex
import os
import sys

PORT = int(os.environ.get("CLAUDE_CLIPBOARD_PORT", 21564))


class ClipboardHandler(BaseHTTPRequestHandler):
    def do_POST(self):
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
    print(f"Test: echo 'hello' | curl -X POST -d @- http://localhost:{port}/copy")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
