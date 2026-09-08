#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}}"
mkdir -p "$STATE_DIR"

MARKER="$STATE_DIR/quick-actions.open"
TARGET_FILE="$STATE_DIR/quick-actions.target"

# Toggle-to-close if popup is already open
if [ -f "$MARKER" ]; then
    python3 "$ROOT/bin/request.py" popup.close >/dev/null 2>&1 || true
    rm -f "$MARKER" "$TARGET_FILE"
    exit 0
fi

# Resolve focused pane
PANE_ID=""
if raw_current=$(python3 "$ROOT/bin/request.py" pane.current '{}' 2>/dev/null); then
    PANE_ID=$(printf '%s' "$raw_current" | jq -r '.pane.pane_id // empty' 2>/dev/null || true)
fi

if [ -z "$PANE_ID" ]; then
    HERDR="${HERDR_BIN_PATH:-herdr}"
    if raw_snap=$("$HERDR" api snapshot 2>/dev/null); then
        PANE_ID=$(printf '%s' "$raw_snap" | jq -r '.result.snapshot.focused_pane_id // empty' 2>/dev/null || true)
    fi
fi

if [ -z "$PANE_ID" ]; then
    echo "open-picker.sh: cannot determine active pane" >&2
    exit 1
fi

# Write target pane atomically
TMP_TARGET=$(mktemp "$STATE_DIR/quick-actions.target.XXXXXX")
printf '%s' "$PANE_ID" > "$TMP_TARGET"
mv "$TMP_TARGET" "$TARGET_FILE"

# Open popup pane
HERDR="${HERDR_BIN_PATH:-herdr}"
PLUGIN_ID="${HERDR_PLUGIN_ID:-codaveto.quick-actions}"

if ! OUT=$("$HERDR" plugin pane open --plugin "$PLUGIN_ID" --entrypoint actions 2>&1); then
    if printf '%s' "$OUT" | grep -q -E "ui_busy|popup already open"; then
        python3 "$ROOT/bin/request.py" popup.close >/dev/null 2>&1 || true
        rm -f "$MARKER" "$TARGET_FILE"
        exit 0
    fi
    echo "open-picker.sh: failed to open popup: $OUT" >&2
    rm -f "$TARGET_FILE"
    exit 1
fi
