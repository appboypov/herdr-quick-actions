#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}}"
mkdir -p "$STATE_DIR"

MARKER="$STATE_DIR/pane-actions.open"
TARGET_FILE="$STATE_DIR/pane-actions.target"
LOG_FILE="$STATE_DIR/pane-actions.log"

HEADER_FILE=$(mktemp "$STATE_DIR/pane-actions.hdr.XXXXXX")
ROWS_FILE=$(mktemp "$STATE_DIR/pane-actions.rows.XXXXXX")

# Mark popup open and register exit cleanup
touch "$MARKER"
cleanup() {
    rm -f "$MARKER" "$TARGET_FILE" "$HEADER_FILE" "$ROWS_FILE"
}
trap cleanup EXIT

# Preflight tools
if ! command -v fzf >/dev/null 2>&1; then
    echo "pane-actions: fzf is required but not found on PATH" >&2
    sleep 3
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "pane-actions: python3 is required but not found on PATH" >&2
    sleep 3
    exit 1
fi

# Read target pane ID
if [ ! -f "$TARGET_FILE" ]; then
    echo "pane-actions: no active target pane recorded" >&2
    sleep 2
    exit 0
fi

TARGET=$(cat "$TARGET_FILE" | tr -d '\n')
if [ -z "$TARGET" ]; then
    echo "pane-actions: target pane is empty" >&2
    sleep 2
    exit 0
fi

# Generate action catalogue
if ! python3 "$ROOT/bin/actions.py" "$TARGET" > "$ROWS_FILE" 2> "$HEADER_FILE"; then
    echo "pane-actions: $(cat "$HEADER_FILE")" >&2
    echo "Press any key to close..."
    read -n 1 -s -r -t 3 || true
    exit 0
fi

HEADER=$(cat "$HEADER_FILE" | head -n 1)

# Run fzf action picker
SELECTION=$(fzf --delimiter=$'\t' --with-nth=3 \
    --prompt='action> ' \
    --header="$HEADER" \
    --height=100% \
    --layout=reverse \
    --info=inline \
    --no-multi \
    --cycle \
    --bind="alt-p:abort" \
    --bind="ctrl-alt-p:abort" \
    --bind="esc:abort" \
    < "$ROWS_FILE" || true)

# If dismissed, exit silently
if [ -z "$SELECTION" ]; then
    exit 0
fi

SPEC=$(printf '%s' "$SELECTION" | cut -f1)
MODE=$(printf '%s' "$SELECTION" | cut -f2)
DISPLAY_NAME=$(printf '%s' "$SELECTION" | cut -f3)

# Handle mode
INPUT_ARG=()

if [[ "$MODE" == prompt:* ]]; then
    PROMPT_LABEL="${MODE#prompt:}"
    echo ""
    read -r -e -p "$PROMPT_LABEL: " USER_INPUT || true
    if [ -z "${USER_INPUT:-}" ]; then
        exit 0
    fi
    INPUT_ARG=(--input "$USER_INPUT")
elif [[ "$MODE" == confirm:* ]]; then
    CONFIRM_Q="${MODE#confirm:}"
    CONFIRM_CHOICE=$(printf "No\nYes" | fzf \
        --prompt="$CONFIRM_Q " \
        --height=20% \
        --layout=reverse \
        --info=hidden \
        --no-multi \
        --cycle || true)
    if [ "$CONFIRM_CHOICE" != "Yes" ]; then
        exit 0
    fi
fi

# Execute action
ERR_TMP=$(mktemp "$STATE_DIR/pane-actions.err.XXXXXX")
OUT_TMP=$(mktemp "$STATE_DIR/pane-actions.out.XXXXXX")

set +e
printf '%s' "$SPEC" | python3 "$ROOT/bin/execute.py" "${INPUT_ARG[@]}" > "$OUT_TMP" 2> "$ERR_TMP"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    ERR_MSG=$(cat "$ERR_TMP")
    rm -f "$ERR_TMP" "$OUT_TMP"

    # Log to file (truncate if > 256 KiB)
    if [ -f "$LOG_FILE" ] && [ "$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)" -gt 262144 ]; then
        tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') [error] $DISPLAY_NAME: $ERR_MSG" >> "$LOG_FILE"

    echo ""
    echo "Action failed: $ERR_MSG" >&2
    echo "Press any key to close..."
    read -n 1 -s -r -t 5 || true
    exit 0
fi

# Show mode output
if [ "$MODE" = "show" ]; then
    echo ""
    cat "$OUT_TMP"
    echo ""
    echo "Press any key to close..."
    read -n 1 -s -r || true
fi

rm -f "$ERR_TMP" "$OUT_TMP"
exit 0
