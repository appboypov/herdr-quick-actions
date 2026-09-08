#!/usr/bin/env python3
"""
Contextual actions catalogue generator for Herdr pane-actions.
Usage: actions.py <target-pane-id>
Outputs tab-delimited rows: <spec-json>\t<mode>\t<display>
Outputs header text on stderr.
"""
import json
import os
import subprocess
import sys

def get_snapshot() -> dict:
    herdr = os.environ.get("HERDR_BIN_PATH") or "herdr"
    try:
        raw = subprocess.check_output(
            [herdr, "api", "snapshot"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        return json.loads(raw)["result"]["snapshot"]
    except Exception as e:
        sys.stderr.write(f"actions.py: failed to fetch snapshot: {e}\n")
        sys.exit(1)

def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        sys.stderr.write("actions.py: missing target pane id argument\n")
        sys.exit(2)

    target_pane_id = sys.argv[1].strip()
    snapshot = get_snapshot()

    panes = snapshot.get("panes", [])
    tabs = snapshot.get("tabs", [])
    workspaces = snapshot.get("workspaces", [])
    agents = snapshot.get("agents", [])

    # Find target pane
    target_pane = next((p for p in panes if p.get("pane_id") == target_pane_id), None)
    if not target_pane:
        sys.stderr.write(f"actions.py: target pane '{target_pane_id}' not found in snapshot\n")
        sys.exit(2)

    target_ws_id = target_pane.get("workspace_id")
    target_tab_id = target_pane.get("tab_id")
    target_label = target_pane.get("label") or target_pane.get("terminal_title_stripped") or target_pane_id
    target_cwd = target_pane.get("cwd") or target_pane.get("foreground_cwd")
    agent_name = target_pane.get("agent")
    agent_status = target_pane.get("agent_status")

    # Workspace info
    current_ws = next((w for w in workspaces if w.get("workspace_id") == target_ws_id), None)
    ws_display = (current_ws.get("label") or current_ws.get("name") or target_ws_id) if current_ws else target_ws_id

    # Tab info
    current_tab = next((t for t in tabs if t.get("tab_id") == target_tab_id), None)
    tab_display = (current_tab.get("label") or f"Tab {current_tab.get('number', '')}") if current_tab else target_tab_id

    # Sibling panes in the same tab
    tab_panes = [p for p in panes if p.get("tab_id") == target_tab_id]
    pane_count = len(tab_panes)
    # Git repo check for worktree operations
    is_git_repo = False
    if target_cwd:
        try:
            p = subprocess.run(
                ["git", "-C", target_cwd, "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True
            )
            is_git_repo = (p.returncode == 0 and p.stdout.strip() == "true")
        except Exception:
            pass

    # Build header string for stderr
    header_parts = [f"pane: {target_pane_id}"]
    if ws_display:
        header_parts.append(ws_display)
    if tab_display:
        header_parts.append(f"/ {tab_display}")
    if target_label and target_label != target_pane_id:
        header_parts.append(f"· {target_label}")
    if agent_name:
        status_str = f" [{agent_status}]" if agent_status else ""
        header_parts.append(f"· {agent_name}{status_str}")
    header_str = " ".join(header_parts)
    sys.stderr.write(f"{header_str}\n")

    # Catalogue rows: list of (spec_dict, mode_str, display_str)
    rows = []

    # 1. Split operations
    split_cwd_arg = {"cwd": target_cwd} if target_cwd else {}
    rows.append((
        {"op": "split", "pane": target_pane_id, "direction": "right", **split_cwd_arg},
        "run",
        "Split right"
    ))
    rows.append((
        {"op": "split", "pane": target_pane_id, "direction": "down", **split_cwd_arg},
        "run",
        "Split down"
    ))

    # 2. Sibling tabs in the same workspace
    sibling_tabs = [t for t in tabs if t.get("workspace_id") == target_ws_id and t.get("tab_id") != target_tab_id]
    for st in sorted(sibling_tabs, key=lambda x: x.get("number", 0)):
        st_id = st.get("tab_id")
        st_label = st.get("label") or f"Tab {st.get('number', '')}"
        rows.append((
            {"op": "move_tab", "pane": target_pane_id, "tab": st_id},
            "run",
            f"Move to tab: {st_label}"
        ))

    # 3. Move to new tab
    rows.append((
        {"op": "new_tab", "pane": target_pane_id},
        "run",
        "Move to new tab"
    ))

    # 4. Other workspaces
    other_workspaces = [w for w in workspaces if w.get("workspace_id") != target_ws_id]
    for ow in sorted(other_workspaces, key=lambda x: x.get("number", 0)):
        ow_id = ow.get("workspace_id")
        ow_label = ow.get("label") or ow.get("name") or ow_id
        rows.append((
            {"op": "move_workspace", "pane": target_pane_id, "workspace": ow_id},
            "run",
            f"Move to workspace: {ow_label}"
        ))

    # 5. Move to new workspace
    rows.append((
        {"op": "new_workspace", "pane": target_pane_id},
        "run",
        "Move to new workspace"
    ))
    # 6. Tab & Workspace management
    rows.append((
        {"op": "create_tab", "workspace": target_ws_id, **split_cwd_arg},
        "run",
        "Create new tab"
    ))
    rows.append((
        {"op": "create_tab", "workspace": target_ws_id, **split_cwd_arg},
        "prompt:New tab label",
        "Create new tab (named...)"
    ))
    rows.append((
        {"op": "create_workspace", **split_cwd_arg},
        "run",
        "Create new workspace"
    ))
    rows.append((
        {"op": "create_workspace", **split_cwd_arg},
        "prompt:New workspace label",
        "Create new workspace (named...)"
    ))
    rows.append((
        {"op": "rename_tab", "tab": target_tab_id},
        "prompt:New tab label",
        f"Rename tab ({tab_display})"
    ))
    rows.append((
        {"op": "rename_workspace", "workspace": target_ws_id},
        "prompt:New workspace label",
        f"Rename workspace ({ws_display})"
    ))

    if is_git_repo:
        rows.append((
            {"op": "worktree_create", "cwd": target_cwd},
            "prompt:Branch name for worktree",
            "Create Git worktree space..."
        ))
    # 6. Swap operations (when tab holds >= 2 panes)
    if pane_count >= 2:
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "left"},
            "run",
            "Swap left"
        ))
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "right"},
            "run",
            "Swap right"
        ))
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "up"},
            "run",
            "Swap up"
        ))
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "down"},
            "run",
            "Swap down"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "right", "amount": 0.1},
            "run",
            "Resize: widen split (+10%)"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "left", "amount": 0.1},
            "run",
            "Resize: narrow split (-10%)"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "down", "amount": 0.1},
            "run",
            "Resize: expand height (+10%)"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "up", "amount": 0.1},
            "run",
            "Resize: shrink height (-10%)"
        ))

    # 7. Zoom toggle
    rows.append((
        {"op": "zoom", "pane": target_pane_id},
        "run",
        "Toggle zoom"
    ))

    # 8. Rename pane
    rows.append((
        {"op": "rename", "pane": target_pane_id},
        "prompt:New pane label",
        "Rename pane"
    ))

    # 9. Agent controls (if agent detected in this pane)
    if agent_name:
        rows.append((
            {"op": "agent_keys", "pane": target_pane_id, "keys": ["ctrl+c"]},
            "run",
            f"Agent: interrupt ({agent_name})"
        ))
        rows.append((
            {"op": "agent_get", "pane": target_pane_id},
            "show",
            f"Agent: status & info ({agent_name})"
        ))
    else:
        rows.append((
            {"op": "agent_start", "pane": target_pane_id, "kind": "omp"},
            "run",
            "Launch agent: omp"
        ))
        rows.append((
            {"op": "agent_start", "pane": target_pane_id, "kind": "claude"},
            "run",
            "Launch agent: claude"
        ))
        rows.append((
            {"op": "agent_start", "pane": target_pane_id, "kind": "pi"},
            "run",
            "Launch agent: pi"
        ))

    # Process control signals
    rows.append((
        {"op": "send_keys", "pane": target_pane_id, "keys": ["ctrl+c"]},
        "run",
        "Send Ctrl+C (Interrupt)"
    ))
    rows.append((
        {"op": "send_keys", "pane": target_pane_id, "keys": ["ctrl+d"]},
        "run",
        "Send Ctrl+D (EOF)"
    ))
    rows.append((
        {"op": "send_keys", "pane": target_pane_id, "keys": ["ctrl+l"]},
        "run",
        "Clear terminal screen"
    ))

    # 10. Copy utilities
    rows.append((
        {"op": "copy", "value": target_pane_id},
        "show",
        f"Copy pane ID ({target_pane_id})"
    ))
    if target_cwd:
        rows.append((
            {"op": "copy", "value": target_cwd},
            "show",
            f"Copy working directory ({target_cwd})"
        ))
    rows.append((
        {"op": "copy_terminal", "pane": target_pane_id, "source": "visible"},
        "show",
        "Copy visible terminal screen"
    ))
    rows.append((
        {"op": "copy_terminal", "pane": target_pane_id, "lines": 50},
        "show",
        "Copy terminal history (last 50 lines)"
    ))

    # 11. Close pane
    rows.append((
        {"op": "close_tab", "tab": target_tab_id},
        f"confirm:Close tab '{tab_display}'?",
        f"Close tab ({tab_display})"
    ))
    rows.append((
        {"op": "close_workspace", "workspace": target_ws_id},
        f"confirm:Close workspace '{ws_display}'?",
        f"Close workspace ({ws_display})"
    ))
    short_label = target_label[:24] if target_label else target_pane_id
    rows.append((
        {"op": "close", "pane": target_pane_id},
        f"confirm:Close pane '{short_label}'?",
        "Close pane"
    ))

    # Print rows to stdout
    for spec, mode, display in rows:
        spec_json = json.dumps(spec, separators=(",", ":"))
        # Ensure display has no literal tabs
        clean_display = display.replace("\t", " ")
        sys.stdout.write(f"{spec_json}\t{mode}\t{clean_display}\n")

if __name__ == "__main__":
    main()
