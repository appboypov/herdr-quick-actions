# Herdr Quick Actions

Modal action palette for the active Herdr pane, bound to `cmd+p`.

Inspects the currently focused pane and presents a flat, one-keystroke action menu in a popup `fzf` palette: moving the pane to other workspaces or tabs, splitting, swapping, zooming, renaming, controlling active agents, or closing the pane.

---

## Why `cmd+p` works this way

Herdr routes all keyboard input to an open popup pane before consulting its direct keybinding table. Additionally, Herdr's legacy key encoder drops `SUPER` (Command) modifiers, so pressing `cmd+p` while a popup is focused transmits a literal `p` to the popup process.

To provide a smooth, toggled experience:

1. **Ghostty** rewrites `cmd+p` into `alt+p` escape bytes (`\x1bp`).
2. **Herdr** binds `alt+p` and `cmd+p` to `appboypov.quick-actions.open`.
3. **fzf** in the popup binds `alt-p:abort` and `ctrl-alt-p:abort`.

The result:
- **1st press of `cmd+p`**: Captures the active pane ID and opens the action palette.
- **2nd press of `cmd+p`**: Immediately dismisses the palette (toggle-close).
- **`Esc`**: Dismisses the palette.

---

## Row names

Every row reads the same way:

```
<Verb phrase>[...] [(subject)] [domain]
```

- **Verb phrase** starts with a capital and never repeats the domain: `Close [pane]`, not `Close pane [pane]`.
- **`...`** marks a row that asks for typed input before it runs.
- **Parentheses** hold only the concrete subject or value acted on: the tab being renamed, the workspace moved into, the value copied, the agent interrupted. Never an explanation.
- **`[domain]`** is the family, last on the line: `pane`, `tab`, `workspace`, `agent`, `plannotator`. Rows are listed in that order, and within a family in the order create, move, inspect, destroy. The Plannotator rows come from a plugin whose Herdr id is `annotate`; the domain word is the tool's name.

So the palette answers two kinds of typing. Type a **domain** to see one family: `workspace` lists everything touching a workspace, including the pane rows that move into one. Type a **verb** to see one operation across families: `split`, `move`, `swap`, `resize`, `rename`, `send`, `copy`, `close`, `create`, `launch`, `review`. Every one of those words is in a label, so every one of them narrows the list. fzf matches the `--with-nth=3` display string, which is the name and nothing else: `copy_terminal`, `plugin_action` and other spec text return no rows.

## Action Catalogue

| Action | Mode | Description |
|---|---|---|
| `Split right` · `Split down` `[pane]` | `run` | Splits the target pane, retaining current directory and following focus. |
| `Move to tab (<label>)` `[pane]` | `run` | Relocates pane into the specified sibling tab with focus. |
| `Move to new tab` `[pane]` | `run` | Moves pane into a newly created tab in the current workspace. |
| `Move to workspace (<ws>)` `[pane]` | `run` | Moves pane into a newly created tab in the target workspace and switches focus. |
| `Move to new workspace` `[pane]` | `run` | Creates a fresh workspace containing only the moved pane and focuses it. |
| `Swap left / right / up / down` `[pane]` | `run` | Swaps positions with an adjacent pane in the same tab. |
| `Resize wider / narrower / taller / shorter` `[pane]` | `run` | Resizes the pane split boundary by 10% in the chosen direction. |
| `Toggle zoom` `[pane]` | `run` | Toggles zoom state on the target pane via socket API. |
| `Rename...` `[pane]` | `prompt` | Prompts for a new pane label in the popup terminal and updates Herdr. |
| `Send Ctrl+C interrupt` `[pane]` | `confirm` | Confirms, then transmits `ctrl+c` to the active pane. |
| `Send Ctrl+D EOF` `[pane]` | `confirm` | Confirms, then transmits `ctrl+d`; a shell exits and the pane closes. |
| `Clear screen` `[pane]` | `run` | Transmits `ctrl+l` to clear the terminal display. |
| `Copy id (<pane>)` · `Copy directory (<cwd>)` `[pane]` | `show` | Copies the value to the system clipboard (`pbcopy`). |
| `Copy visible screen` `[pane]` | `show` | Captures visible terminal content and copies to clipboard. |
| `Copy history (last 50 lines)` `[pane]` | `show` | Captures the last 50 lines of terminal history and copies them. |
| `Copy history...` `[pane]` | `prompt` | Prompts for a line count, then copies that many lines of history. |
| `Close` `[pane]` | `confirm` | Prompts confirmation before closing the pane. |
| `Create` `[tab]` · `Create` `[workspace]` | `run` | Creates a fresh focused tab or workspace, inheriting working directory. |
| `Create...` `[tab]` · `Create...` `[workspace]` | `prompt` | Prompts for a label, then creates it focused. |
| `Rename... (<subject>)` `[tab]` `[workspace]` | `prompt` | Prompts for a new label and renames the active tab or workspace. |
| `Create Git worktree...` `[workspace]` | `prompt` | Prompts for a branch name and creates an isolated Git worktree space. |
| `Close (<subject>)` `[tab]` `[workspace]` | `confirm` | Prompts confirmation before closing the active tab or workspace. |
| `Launch omp / claude / pi` `[agent]` | `run` | Starts an interactive AI coding agent inside an empty shell pane. |
| `Interrupt (<agent>)` `[agent]` | `confirm` | Confirms, then sends `SIGINT` to the agent running in the pane, dropping its current work. |
| `Status & info (<agent>)` `[agent]` | `show` | Displays agent details, session ID, and status. |
| `Comment on selection` · `Copy annotations` · `Copy annotations and archive` · `Manage annotations` · `Review this folder` · `Review agent's last reply` `[plannotator]` | `run` | Invokes an action of the installed Plannotator plugin (`annotate` in Herdr). Rows are read live from `herdr plugin action list`, so they disappear with the plugin, and their names are restated in this palette's grammar. Herdr allows one popup at a time, so the invocation is detached: it waits for this palette to close, refocuses the target pane, then invokes. |

---

## Configuration

### 1. Ghostty (`~/.config/ghostty/config`)

```text
# Herdr quick actions popup toggle: send alt+p bytes so chord survives Herdr's
# legacy encoder and reaches the popup process (super is stripped there).
keybind = super+p=text:\x1bp
```

Reload Ghostty with `cmd+shift+,`.

### 2. Herdr (`~/.config/herdr/config.toml`)

```toml
[[keys.command]]
key = "cmd+p"
type = "plugin_action"
command = "appboypov.quick-actions.open"
description = "quick actions"

[[keys.command]]
key = "alt+p"
type = "plugin_action"
command = "appboypov.quick-actions.open"
description = "quick actions"

[[keys.command]]
key = "ctrl+alt+p"
type = "plugin_action"
command = "appboypov.quick-actions.open"
description = "quick actions"
```

Reload Herdr config:
```bash
herdr server reload-config
```

---

## Installation

```bash
herdr plugin link /Users/codaveto/hq/das/ai/repos/herdr-quick-actions
herdr server reload-config
```

Verify with:
```bash
herdr plugin list
```

---

## Architecture

- `herdr-plugin.toml`: Plugin manifest declaring action `open` and popup pane `actions`.
- `bin/open-picker.sh`: Captures target pane ID from `pane.current` before popup launch and passes it via state directory.
- `bin/actions.py`: Projects live session snapshot (`herdr api snapshot`) into flat contextual action rows.
- `bin/picker.sh`: Interactive `fzf` runner with reverse layout, context header, dismiss chords, and mode dispatch.
- `bin/execute.py`: Dispatches operations to native `herdr` CLI commands targeting the explicit pane ID.
- `bin/request.py`: Unix socket client for `popup.close` and `pane.zoom`.
