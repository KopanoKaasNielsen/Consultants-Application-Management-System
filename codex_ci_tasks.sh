#!/usr/bin/env bash
# Codex CI automation script
# Automatically runs GPT-5 Codex tasks on PRs or main branch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# Detect a Python interpreter to use for running the helper scripts.
if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [[ -x "$BASE_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$BASE_DIR/.venv/bin/python"
elif [[ -x "$BASE_DIR/venv/bin/python" ]]; then
  PYTHON_BIN="$BASE_DIR/venv/bin/python"
else
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "Unable to locate a python interpreter." >&2
    exit 1
  fi
fi

RESULTS_DIR="$BASE_DIR/results"
REVIEWS_DIR="$BASE_DIR/reviews"

mkdir -p "$RESULTS_DIR" "$REVIEWS_DIR"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

PR_URL="${1:-}"

if [[ -z "$PR_URL" ]]; then
  log "No PR URL provided — running local tests and lint."
  log "🧪 Running pytest..."
  "$PYTHON_BIN" "$BASE_DIR/codex_agent.py" "Run pytest in this project and summarize results." >> "$RESULTS_DIR/test_summary.txt"

  log "🧹 Running flake8 lint check..."
  "$PYTHON_BIN" "$BASE_DIR/codex_agent.py" "Run flake8 and summarize key issues." >> "$RESULTS_DIR/lint_summary.txt"

  log "✅ Local Codex CI checks complete. Results saved to $RESULTS_DIR/"
  exit 0
fi

log "🚀 Codex CI Review Triggered for: $PR_URL"

# --- Step 1: Run GPT-5 Review ---
"$PYTHON_BIN" "$BASE_DIR/codex_review.py" "$PR_URL"
REVIEW_FILE=$(ls -t "$REVIEWS_DIR"/*.md 2>/dev/null | head -n 1)
log "🧠 Review complete — saved to $REVIEW_FILE"

# --- Step 2: Run Tests ---
"$PYTHON_BIN" "$BASE_DIR/codex_agent.py" "Run pytest and summarize test outcomes." >> "$RESULTS_DIR/test_summary.txt"
log "🧪 Test summary saved."

# --- Step 3: Run Lint Check ---
"$PYTHON_BIN" "$BASE_DIR/codex_agent.py" "Run flake8 and summarize findings." >> "$RESULTS_DIR/lint_summary.txt"
log "🧹 Lint summary saved."

# --- Step 4: Generate Fix Proposal (optional) ---
"$PYTHON_BIN" "$BASE_DIR/codex_fix.py" "$PR_URL" | tee "$RESULTS_DIR/fix_output.log"

log "✅ Codex CI run complete for: $PR_URL"
log "Results stored under: $RESULTS_DIR/"
