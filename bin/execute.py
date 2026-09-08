#!/usr/bin/env python3
"""
Execution dispatcher for Herdr pane-actions.
Reads a single JSON action spec from stdin, optional --input <text>.
Executes the corresponding Herdr CLI or socket API call.

Exit codes:
0: Success
1: Herdr rejected operation (error printed on stderr)
2: Malformed or unknown spec (error printed on stderr)
3: Target pane not found
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

# Add bin/ to sys.path so we can import request
BIN_DIR = os.path.dirname(os.path.abspath(__file__))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import request

HERDR_BIN = os.environ.get("HERDR_BIN_PATH") or "herdr"

class ExecutionError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code

def run_herdr(args: list[str]) -> dict:
    """Runs herdr CLI subcommand with JSON output if possible or plain."""
    cmd = [HERDR_BIN] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        raise ExecutionError(f"Failed to execute {' '.join(cmd)}: {e}", code=1)

    if p.returncode != 0:
        err_msg = p.stderr.strip() or p.stdout.strip() or f"Process exited with code {p.returncode}"
        raise ExecutionError(err_msg, code=1)

    out = p.stdout.strip()
    if out.startswith("{") and out.endswith("}"):
        try:
            return json.loads(out)
        except Exception:
            pass
    return {"raw": out}

# ==================== HANDLERS ====================

def handle_split(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    direction = spec.get("direction", "right")
    cwd = spec.get("cwd")

    args = ["pane", "split", pane_id, "--direction", direction, "--focus"]
    if cwd:
        args.extend(["--cwd", cwd])

    run_herdr(args)
    return f"Pane {pane_id} split {direction}"

def handle_zoom(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    mode = spec.get("mode", "toggle")
    res = request.call("pane.zoom", {"pane_id": pane_id, "mode": mode})
    if "error" in res and res["error"]:
        err = res["error"]
        msg = err.get("message") or str(err)
        raise ExecutionError(f"Zoom failed: {msg}", code=1)
    return f"Toggled zoom for {pane_id}"

def handle_copy(spec: dict, input_text: str | None) -> str:
    value = str(spec.get("value", ""))
    clipboard_cmd = None
    if shutil.which("pbcopy"):
        clipboard_cmd = ["pbcopy"]
    elif shutil.which("wl-copy"):
        clipboard_cmd = ["wl-copy"]
    elif shutil.which("xclip"):
        clipboard_cmd = ["xclip", "-selection", "clipboard"]

    if clipboard_cmd:
        p = subprocess.run(clipboard_cmd, input=value, text=True, capture_output=True)
        if p.returncode == 0:
            return f"Copied to clipboard: {value}"

    # Fallback: print to stdout
    return f"Value: {value}"

def handle_agent_get(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    res = run_herdr(["agent", "get", pane_id])
    if "result" in res and "agent" in res["result"]:
        agent_data = res["result"]["agent"]
        lines = [f"Agent in {pane_id}:"]
        for k, v in agent_data.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    return res.get("raw") or f"Agent in {pane_id} retrieved"

def handle_agent_keys(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    keys = spec.get("keys", ["ctrl+c"])
    run_herdr(["agent", "send-keys", pane_id] + keys)
    return f"Sent keys {' '.join(keys)} to {pane_id}"

def handle_swap(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    direction = spec.get("direction", "right")
    run_herdr(["pane", "swap", "--pane", pane_id, "--direction", direction])
    return f"Swapped {pane_id} {direction}"

def handle_move_workspace(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    target_ws = spec["workspace"]
    run_herdr(["pane", "move", pane_id, "--new-tab", "--workspace", target_ws, "--focus"])
    return f"Moved {pane_id} to workspace {target_ws}"

def handle_move_tab(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    target_tab = spec["tab"]
    run_herdr(["pane", "move", pane_id, "--tab", target_tab, "--split", "right", "--focus"])
    return f"Moved {pane_id} to tab {target_tab}"

def handle_new_workspace(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    run_herdr(["pane", "move", pane_id, "--new-workspace", "--focus"])
    return f"Moved {pane_id} to new workspace"

def handle_new_tab(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    run_herdr(["pane", "move", pane_id, "--new-tab", "--focus"])
    return f"Moved {pane_id} to new tab"
def handle_rename(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    new_label = (input_text or "").strip()
    if not new_label:
        raise ExecutionError("Rename cancelled: new label cannot be empty", code=2)
    run_herdr(["pane", "rename", pane_id, new_label])
    return f"Renamed {pane_id} to '{new_label}'"

def handle_close(spec: dict, input_text: str | None) -> str:
    pane_id = spec["pane"]
    run_herdr(["pane", "close", pane_id])
    return f"Closed pane {pane_id}"
def handle_create_tab(spec: dict, input_text: str | None) -> str:
    args = ["tab", "create", "--focus"]
    ws = spec.get("workspace")
    if ws:
        args.extend(["--workspace", ws])
    cwd = spec.get("cwd")
    if cwd:
        args.extend(["--cwd", cwd])
    label = (input_text or "").strip()
    if label:
        args.extend(["--label", label])
    res = run_herdr(args)
    tab_info = res.get("result", {}).get("tab", {})
    return f"Created tab {tab_info.get('tab_id', '')} with focus"

def handle_create_workspace(spec: dict, input_text: str | None) -> str:
    args = ["workspace", "create", "--focus"]
    cwd = spec.get("cwd")
    if cwd:
        args.extend(["--cwd", cwd])
    label = (input_text or "").strip()
    if label:
        args.extend(["--label", label])
    res = run_herdr(args)
    ws_info = res.get("result", {}).get("workspace", {})
    return f"Created workspace {ws_info.get('workspace_id', '')} with focus"

def handle_rename_tab(spec: dict, input_text: str | None) -> str:
    tab_id = spec["tab"]
    new_label = (input_text or "").strip()
    if not new_label:
        raise ExecutionError("Rename cancelled: new tab label cannot be empty", code=2)
    run_herdr(["tab", "rename", tab_id, new_label])
    return f"Renamed tab {tab_id} to '{new_label}'"

def handle_rename_workspace(spec: dict, input_text: str | None) -> str:
    ws_id = spec["workspace"]
    new_label = (input_text or "").strip()
    if not new_label:
        raise ExecutionError("Rename cancelled: new workspace label cannot be empty", code=2)
    run_herdr(["workspace", "rename", ws_id, new_label])
    return f"Renamed workspace {ws_id} to '{new_label}'"

def handle_close_tab(spec: dict, input_text: str | None) -> str:
    tab_id = spec["tab"]
    run_herdr(["tab", "close", tab_id])
    return f"Closed tab {tab_id}"

def handle_close_workspace(spec: dict, input_text: str | None) -> str:
    ws_id = spec["workspace"]
    run_herdr(["workspace", "close", ws_id])
    return f"Closed workspace {ws_id}"

OPS = {
    "split": handle_split,
    "zoom": handle_zoom,
    "copy": handle_copy,
    "agent_get": handle_agent_get,
    "agent_keys": handle_agent_keys,
    "swap": handle_swap,
    "rename": handle_rename,
    "close": handle_close,
    "move_workspace": handle_move_workspace,
    "move_tab": handle_move_tab,
    "new_workspace": handle_new_workspace,
    "new_tab": handle_new_tab,
    "create_tab": handle_create_tab,
    "create_workspace": handle_create_workspace,
    "rename_tab": handle_rename_tab,
    "rename_workspace": handle_rename_workspace,
    "close_tab": handle_close_tab,
    "close_workspace": handle_close_workspace,
}

def main():
    parser = argparse.ArgumentParser(description="Herdr pane action executor")
    parser.add_argument("--input", dest="input_text", help="Text input from prompt mode", default=None)
    args = parser.parse_args()

    raw = sys.stdin.read().strip()
    if not raw:
        sys.stderr.write("execute.py: empty spec on stdin\n")
        sys.exit(2)

    try:
        spec = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"execute.py: invalid JSON spec: {e}\n")
        sys.exit(2)

    op = spec.get("op")
    if not op or op not in OPS:
        sys.stderr.write(f"execute.py: unknown or missing op '{op}'\n")
        sys.exit(2)

    handler = OPS[op]
    try:
        result_msg = handler(spec, args.input_text)
        if result_msg:
            print(result_msg)
        sys.exit(0)
    except ExecutionError as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(e.code)
    except Exception as e:
        sys.stderr.write(f"execute.py error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
