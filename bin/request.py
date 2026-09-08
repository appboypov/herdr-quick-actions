#!/usr/bin/env python3
"""
Thin socket API client for Herdr.
Sends a single JSON request to HERDR_SOCKET_PATH and prints the result.
"""
import json
import os
import socket
import sys

def find_socket() -> str:
    path = os.environ.get("HERDR_SOCKET_PATH")
    if path and os.path.exists(path):
        return path
    session = os.environ.get("HERDR_SESSION")
    if not session:
        sys.stderr.write("request.py: neither HERDR_SOCKET_PATH nor HERDR_SESSION is set\n")
        sys.exit(1)
    cand = f"/tmp/herdr-{session}.sock"
    if os.path.exists(cand):
        return cand
    cand = os.path.expanduser(f"~/.local/state/herdr/{session}.sock")
    if os.path.exists(cand):
        return cand
    sys.stderr.write(f"request.py: cannot find socket for session {session}\n")
    sys.exit(1)

def call(method: str, params: dict) -> dict:
    sock_path = find_socket()
    req = {
        "id": f"herdr-pane-actions:{method}",
        "method": method,
        "params": params,
    }
    raw = (json.dumps(req) + "\n").encode("utf-8")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(sock_path)
        s.sendall(raw)
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        line = buf.split(b"\n", 1)[0].decode("utf-8")
        if not line:
            return {"error": {"message": "empty response from server"}}
        return json.loads(line)
    finally:
        s.close()

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: request.py <method> [params-json]\n")
        sys.exit(2)
    method = sys.argv[1]
    params = {}
    if len(sys.argv) >= 3 and sys.argv[2]:
        params = json.loads(sys.argv[2])
    res = call(method, params)
    if "error" in res and res["error"]:
        sys.stderr.write(json.dumps(res["error"]) + "\n")
        sys.exit(1)
    print(json.dumps(res.get("result", {})))

if __name__ == "__main__":
    main()
