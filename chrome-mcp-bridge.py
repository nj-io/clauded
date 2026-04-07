#!/usr/bin/env python3
"""
Chrome MCP bridge — runs on your Mac, proxies the Claude-in-Chrome MCP server
to Docker containers via HTTP.

Spawns `claude --claude-in-chrome-mcp` as a persistent subprocess and translates
between HTTP (from Docker) and stdio (to the MCP process).

Start:  python3 chrome-mcp-bridge.py
        python3 chrome-mcp-bridge.py --port 21565

Usage from container:
        curl -X POST -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
          http://host.docker.internal:21565/mcp
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import threading
import json
import os
import sys
import time

PORT = int(os.environ.get("CLAUDE_CHROME_MCP_PORT", 21565))

# Find the claude binary
CLAUDE_BIN = None
for path in [
    os.path.expanduser("~/.local/bin/claude"),
    "/usr/local/bin/claude",
]:
    if os.path.exists(path):
        CLAUDE_BIN = path
        break


class McpProcess:
    """Manages a persistent claude --claude-in-chrome-mcp subprocess."""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.initialized = False

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        self.proc = subprocess.Popen(
            [CLAUDE_BIN, "--claude-in-chrome-mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.initialized = False
        # Send MCP initialize handshake
        init_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": "__bridge_init__",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "chrome-mcp-bridge", "version": "1.0"},
            },
        })
        self._send_raw(init_msg)
        resp = self._read_line()
        if resp:
            self.initialized = True
            # Send initialized notification
            notif = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            })
            self._send_raw(notif)

    def _send_raw(self, line):
        if self.proc and self.proc.poll() is None:
            self.proc.stdin.write((line + "\n").encode())
            self.proc.stdin.flush()

    def _read_line(self):
        if self.proc and self.proc.poll() is None:
            line = self.proc.stdout.readline()
            if line:
                return line.decode().strip()
        return None

    def send(self, message):
        """Send a JSON-RPC message and return the response."""
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                self.start()
            if not self.initialized:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32000, "message": "MCP process not initialized"},
                })
            self._send_raw(json.dumps(message))
            resp = self._read_line()
            return resp if resp else json.dumps({
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {"code": -32000, "message": "No response from MCP process"},
            })

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.initialized = False


mcp = McpProcess()


class BridgeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "invalid JSON"}')
            return

        # Skip initialize/initialized — the bridge handles that internally
        method = message.get("method", "")
        if method == "initialize":
            # Return our cached init response
            resp = json.dumps({
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "logging": {}},
                    "serverInfo": {"name": "Claude in Chrome (bridged)", "version": "1.0.0"},
                },
            })
        elif method == "notifications/initialized":
            resp = ""
        else:
            resp = mcp.send(message)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if resp:
            self.wfile.write(resp.encode())

    def do_GET(self):
        # Health check
        alive = mcp.proc and mcp.proc.poll() is None and mcp.initialized
        self.send_response(200 if alive else 503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok" if alive else "not running",
            "initialized": mcp.initialized,
        }).encode())

    def log_message(self, format, *args):
        pass  # Silent


def main():
    if not CLAUDE_BIN:
        print("Error: claude binary not found")
        sys.exit(1)

    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    # Start the MCP process
    mcp.start()
    if mcp.initialized:
        print(f"Chrome MCP bridge listening on port {port}")
        print(f"MCP process started and initialized")
        print(f"Health: curl http://localhost:{port}/")
        print(f"Test:   curl -X POST -H 'Content-Type: application/json' "
              f"-d '{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{{}}}}' "
              f"http://localhost:{port}/mcp")
    else:
        print(f"Warning: MCP process failed to initialize, will retry on first request")
        print(f"Chrome MCP bridge listening on port {port}")

    server = HTTPServer(("0.0.0.0", port), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        mcp.stop()
        print("Stopped.")


if __name__ == "__main__":
    main()
