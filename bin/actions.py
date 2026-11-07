#!/usr/bin/env python3
"""
Contextual actions catalogue generator for Herdr quick-actions.
Usage: actions.py <target-pane-id>
Outputs tab-delimited rows: <spec-json>\t<mode>\t<display>
Outputs header text on stderr.
"""
import json
import os
import subprocess
import sys

# Every row reads "<Verb phrase>[...] [(subject)] [domain]": the verb phrase never
# repeats the domain, "..." marks a row that asks for typed input, parentheses hold
# only the concrete subject or value acted on, and the domain is the word to type to
# see the whole family. Rows are emitted in this domain order.
DOMAINS = ("pane", "tab", "workspace", "agent", "plannotator")

# Herdr's plugin id is "annotate"; the tool is Plannotator, so that is the domain word
# shown and typed. Its manifest titles are written for Herdr's own action menu, so they
# are restated here in the palette's grammar. An action without an entry falls back to
# its manifest title.
PLANNOTATOR_PLUGIN_ID = "annotate"
PLANNOTATOR_PHRASES = {
    "capture": "Comment on selection",
    "copy-context": "Copy annotations",
    "copy-archive": "Copy annotations and archive",
    "manage": "Manage annotations",
    "open": "Review this folder",
    "last": "Review agent's last reply",
}

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

def get_plannotator_actions() -> list[tuple[str, str]]:
    """Actions of the installed Plannotator plugin.

    Read live, so uninstalling the plugin removes the rows and a new action
    appears without touching this file. The link handler's own action is
    skipped: it needs a Ctrl-clicked file:// link as its context.
    """
    herdr = os.environ.get("HERDR_BIN_PATH") or "herdr"
    try:
        raw = subprocess.check_output(
            [herdr, "plugin", "action", "list"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        actions = json.loads(raw)["result"]["actions"]
    except Exception:
        return []

    found = []
    for action in actions:
        if action.get("plugin_id") != PLANNOTATOR_PLUGIN_ID:
            continue
        action_id = action.get("action_id")
        if not action_id or action_id == "open-link":
            continue
        found.append((action_id, action.get("title") or action_id))

    order = list(PLANNOTATOR_PHRASES)
    return sorted(
        found,
        key=lambda pair: order.index(pair[0]) if pair[0] in order else len(order)
    )

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
        "Split right [pane]"
    ))
    rows.append((
        {"op": "split", "pane": target_pane_id, "direction": "down", **split_cwd_arg},
        "run",
        "Split down [pane]"
    ))

    # 2. Sibling tabs in the same workspace
    sibling_tabs = [t for t in tabs if t.get("workspace_id") == target_ws_id and t.get("tab_id") != target_tab_id]
    for st in sorted(sibling_tabs, key=lambda x: x.get("number", 0)):
        st_id = st.get("tab_id")
        st_label = st.get("label") or f"Tab {st.get('number', '')}"
        rows.append((
            {"op": "move_tab", "pane": target_pane_id, "tab": st_id},
            "run",
            f"Move to tab ({st_label}) [pane]"
        ))

    # 3. Move to new tab
    rows.append((
        {"op": "new_tab", "pane": target_pane_id},
        "run",
        "Move to new tab [pane]"
    ))

    # 4. Other workspaces
    other_workspaces = [w for w in workspaces if w.get("workspace_id") != target_ws_id]
    for ow in sorted(other_workspaces, key=lambda x: x.get("number", 0)):
        ow_id = ow.get("workspace_id")
        ow_label = ow.get("label") or ow.get("name") or ow_id
        rows.append((
            {"op": "move_workspace", "pane": target_pane_id, "workspace": ow_id},
            "run",
            f"Move to workspace ({ow_label}) [pane]"
        ))

    # 5. Move to new workspace
    rows.append((
        {"op": "new_workspace", "pane": target_pane_id},
        "run",
        "Move to new workspace [pane]"
    ))
    # 6. Tab & Workspace management
    rows.append((
        {"op": "create_tab", "workspace": target_ws_id, **split_cwd_arg},
        "run",
        "Create [tab]"
    ))
    rows.append((
        {"op": "create_tab", "workspace": target_ws_id, **split_cwd_arg},
        "prompt:New tab label",
        "Create... [tab]"
    ))
    rows.append((
        {"op": "create_workspace", **split_cwd_arg},
        "run",
        "Create [workspace]"
    ))
    rows.append((
        {"op": "create_workspace", **split_cwd_arg},
        "prompt:New workspace label",
        "Create... [workspace]"
    ))
    rows.append((
        {"op": "rename_tab", "tab": target_tab_id},
        "prompt:New tab label",
        f"Rename... ({tab_display}) [tab]"
    ))
    rows.append((
        {"op": "rename_workspace", "workspace": target_ws_id},
        "prompt:New workspace label",
        f"Rename... ({ws_display}) [workspace]"
    ))

    if is_git_repo:
        rows.append((
            {"op": "worktree_create", "cwd": target_cwd},
            "prompt:Branch name for worktree",
            "Create Git worktree... [workspace]"
        ))
    # 6. Swap operations (when tab holds >= 2 panes)
    if pane_count >= 2:
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "left"},
            "run",
            "Swap left [pane]"
        ))
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "right"},
            "run",
            "Swap right [pane]"
        ))
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "up"},
            "run",
            "Swap up [pane]"
        ))
        rows.append((
            {"op": "swap", "pane": target_pane_id, "direction": "down"},
            "run",
            "Swap down [pane]"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "right", "amount": 0.1},
            "run",
            "Resize wider (+10%) [pane]"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "left", "amount": 0.1},
            "run",
            "Resize narrower (-10%) [pane]"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "down", "amount": 0.1},
            "run",
            "Resize taller (+10%) [pane]"
        ))
        rows.append((
            {"op": "resize", "pane": target_pane_id, "direction": "up", "amount": 0.1},
            "run",
            "Resize shorter (-10%) [pane]"
        ))

    # 7. Zoom toggle
    rows.append((
        {"op": "zoom", "pane": target_pane_id},
        "run",
        "Toggle zoom [pane]"
    ))

    # 8. Rename pane
    rows.append((
        {"op": "rename", "pane": target_pane_id},
        "prompt:New pane label",
        "Rename... [pane]"
    ))

    # 9. Agent controls (if agent detected in this pane)
    if agent_name:
        rows.append((
            {"op": "agent_keys", "pane": target_pane_id, "keys": ["ctrl+c"]},
            f"confirm:Interrupt {agent_name} and drop its current work?",
            f"Interrupt ({agent_name}) [agent]"
        ))
        rows.append((
            {"op": "agent_get", "pane": target_pane_id},
            "show",
            f"Status & info ({agent_name}) [agent]"
        ))
    else:
        rows.append((
            {"op": "agent_start", "pane": target_pane_id, "kind": "omp"},
            "run",
            "Launch omp [agent]"
        ))
        rows.append((
            {"op": "agent_start", "pane": target_pane_id, "kind": "claude"},
            "run",
            "Launch claude [agent]"
        ))
        rows.append((
            {"op": "agent_start", "pane": target_pane_id, "kind": "pi"},
            "run",
            "Launch pi [agent]"
        ))

    # 9b. Plannotator actions (terminal annotations and document review)
    for action_id, title in get_plannotator_actions():
        phrase = PLANNOTATOR_PHRASES.get(action_id) or title[:1].upper() + title[1:]
        rows.append((
            {
                "op": "plugin_action",
                "plugin": PLANNOTATOR_PLUGIN_ID,
                "action": action_id,
                "pane": target_pane_id,
            },
            "run",
            f"{phrase} [plannotator]"
        ))

    # Process control signals
    rows.append((
        {"op": "send_keys", "pane": target_pane_id, "keys": ["ctrl+c"]},
        f"confirm:Interrupt whatever is running in '{target_label[:24]}'?",
        "Send Ctrl+C interrupt [pane]"
    ))
    rows.append((
        {"op": "send_keys", "pane": target_pane_id, "keys": ["ctrl+d"]},
        f"confirm:Send EOF to '{target_label[:24]}'? A shell exits and the pane closes",
        "Send Ctrl+D EOF [pane]"
    ))
    rows.append((
        {"op": "send_keys", "pane": target_pane_id, "keys": ["ctrl+l"]},
        "run",
        "Clear screen [pane]"
    ))

    # 10. Copy utilities
    rows.append((
        {"op": "copy", "value": target_pane_id},
        "show",
        f"Copy id ({target_pane_id}) [pane]"
    ))
    if target_cwd:
        rows.append((
            {"op": "copy", "value": target_cwd},
            "show",
            f"Copy directory ({target_cwd}) [pane]"
        ))
    rows.append((
        {"op": "copy_terminal", "pane": target_pane_id, "source": "visible"},
        "show",
        "Copy visible screen [pane]"
    ))
    rows.append((
        {"op": "copy_terminal", "pane": target_pane_id, "lines": 50},
        "show",
        "Copy history (last 50 lines) [pane]"
    ))
    rows.append((
        {"op": "copy_terminal", "pane": target_pane_id},
        "prompt:Number of history lines",
        "Copy history... [pane]"
    ))

    # 11. Close pane
    rows.append((
        {"op": "close_tab", "tab": target_tab_id},
        f"confirm:Close tab '{tab_display}'?",
        f"Close ({tab_display}) [tab]"
    ))
    rows.append((
        {"op": "close_workspace", "workspace": target_ws_id},
        f"confirm:Close workspace '{ws_display}'?",
        f"Close ({ws_display}) [workspace]"
    ))
    short_label = target_label[:24] if target_label else target_pane_id
    rows.append((
        {"op": "close", "pane": target_pane_id},
        f"confirm:Close pane '{short_label}'?",
        "Close [pane]"
    ))

    # Print rows to stdout, grouped by domain. Sorting is stable, so each domain keeps
    # the order it was built in: create, move, inspect, destroy.
    def domain_rank(row) -> int:
        display = row[2]
        for index, domain in enumerate(DOMAINS):
            if display.endswith(f"[{domain}]"):
                return index
        return len(DOMAINS)

    for spec, mode, display in sorted(rows, key=domain_rank):
        spec_json = json.dumps(spec, separators=(",", ":"))
        # Ensure display has no literal tabs
        clean_display = display.replace("\t", " ")
        sys.stdout.write(f"{spec_json}\t{mode}\t{clean_display}\n")

if __name__ == "__main__":
    main()
