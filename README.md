# Herdr Pane Actions

Modal action palette for the active Herdr pane, bound to `cmd+p`.

Inspects the currently focused pane and presents a flat, one-keystroke action menu in a popup `fzf` palette: moving the pane to other workspaces or tabs, splitting, swapping, zooming, renaming, controlling active agents, or closing the pane.

---

## Why `cmd+p` works this way

Herdr routes all keyboard input to an open popup pane before consulting its direct keybinding table. Additionally, Herdr's legacy key encoder drops `SUPER` (Command) modifiers, so pressing `cmd+p` while a popup is focused transmits a literal `p` to the popup process.

To provide a smooth, toggled experience:

1. **Ghostty** rewrites `cmd+p` into `alt+p` escape bytes (`\x1bp`).
2. **Herdr** binds `alt+p` and `cmd+p` to `codaveto.pane-actions.open`.
3. **fzf** in the popup binds `alt-p:abort` and `ctrl-alt-p:abort`.

The result:
- **1st press of `cmd+p`**: Captures the active pane ID and opens the action palette.
- **2nd press of `cmd+p`**: Immediately dismisses the palette (toggle-close).
- **`Esc`**: Dismisses the palette.

---

## Action Catalogue

| Action | Mode | Description |
|---|---|---|
| `Split right` | `run` | Splits target pane to the right, retaining current directory and following focus. |
| `Split down` | `run` | Splits target pane downwards, retaining current directory and following focus. |
| `Move to tab: <label>` | `run` | Relocates pane into the specified sibling tab with focus. |
| `Move to new tab` | `run` | Moves pane into a newly created tab in the current workspace. |
| `Move to workspace: <ws>` | `run` | Moves pane into a newly created tab in the target workspace and switches focus. |
| `Move to new workspace` | `run` | Creates a fresh workspace containing only the moved pane and focuses it. |
| `Create new tab` | `run` | Creates a fresh tab in the current workspace with focus, inheriting working directory. |
| `Create new tab (named...)` | `prompt` | Prompts for a label and creates a fresh focused tab in the current workspace. |
| `Create new workspace` | `run` | Creates a fresh workspace with focus, inheriting working directory. |
| `Create new workspace (named...)` | `prompt` | Prompts for a label and creates a fresh focused workspace. |
| `Create Git worktree space...` | `prompt` | Prompts for a branch name and creates an isolated Git worktree space. |
| `Rename tab` | `prompt` | Prompts for a new label and renames the active tab. |
| `Rename workspace` | `prompt` | Prompts for a new label and renames the active workspace. |
| `Swap left / right / up / down` | `run` | Swaps positions with an adjacent pane in the same tab. |
| `Resize: widen / narrow / expand / shrink` | `run` | Resizes pane split boundary by 10% in the chosen direction. |
| `Toggle zoom` | `run` | Toggles zoom state on the target pane via socket API. |
| `Rename pane` | `prompt` | Prompts for a new pane label in the popup terminal and updates Herdr. |
| `Launch agent: omp / claude / pi` | `run` | Starts an interactive AI coding agent inside an empty shell pane. |
| `Agent: interrupt` | `run` | Sends `SIGINT` (`ctrl+c`) to an active agent running in the pane. |
| `Agent: status & info` | `show` | Displays agent details, session ID, and status. |
| `Send Ctrl+C (Interrupt)` | `run` | Transmits `ctrl+c` to the active pane. |
| `Send Ctrl+D (EOF)` | `run` | Transmits `ctrl+d` to exit shells, REPLs, or stdin readers. |
| `Clear terminal screen` | `run` | Transmits `ctrl+l` to clear the terminal display. |
| `Copy visible terminal screen` | `show` | Captures visible terminal content and copies to clipboard (`pbcopy`). |
| `Copy terminal history (last 50 lines)` | `show` | Captures recent terminal history and copies to clipboard. |
| `Copy pane ID` | `show` | Copies target pane ID to system clipboard (`pbcopy`). |
| `Copy working directory` | `show` | Copies target pane's working directory to clipboard. |
| `Close tab` | `confirm` | Prompts confirmation before closing the active tab. |
| `Close workspace` | `confirm` | Prompts confirmation before closing the active workspace. |
| `Close pane` | `confirm` | Prompts confirmation before closing the pane. |

---

## Configuration

### 1. Ghostty (`~/.config/ghostty/config`)

```text
# Herdr pane actions popup toggle: send alt+p bytes so chord survives Herdr's
# legacy encoder and reaches the popup process (super is stripped there).
keybind = super+p=text:\x1bp
```

Reload Ghostty with `cmd+shift+,`.

### 2. Herdr (`~/.config/herdr/config.toml`)

```toml
[[keys.command]]
key = "cmd+p"
type = "plugin_action"
command = "codaveto.pane-actions.open"
description = "pane actions"

[[keys.command]]
key = "alt+p"
type = "plugin_action"
command = "codaveto.pane-actions.open"
description = "pane actions"

[[keys.command]]
key = "ctrl+alt+p"
type = "plugin_action"
command = "codaveto.pane-actions.open"
description = "pane actions"
```

Reload Herdr config:
```bash
herdr server reload-config
```

---

## Installation

```bash
herdr plugin link /Users/codaveto/Repos/herdr-pane-actions
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
