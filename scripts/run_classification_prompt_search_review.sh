#!/bin/sh
# User-started sequential smoke/full run. Repeat this command to resume safely.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_LOG_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-classification-prompt-validation-v3/launch"
mkdir -p "$KBA_LOG_DIR"
printf '%s\n' "Running validation-only smoke; log: $KBA_LOG_DIR/smoke.log"
sh "$KBA_PROJECT_DIR/scripts/run_classification_prompt_search.sh" \
  --limit_questions 3 \
  --run_dir "$KBA_PROJECT_DIR/runs/qwen2.5-3b-classification-prompt-validation-smoke-v3" \
  >> "$KBA_LOG_DIR/smoke.log" 2>&1
printf '%s\n' "Smoke passed. Running full validation; log: $KBA_LOG_DIR/full.log"
sh "$KBA_PROJECT_DIR/scripts/run_classification_prompt_search.sh" \
  --run_dir "$KBA_PROJECT_DIR/runs/qwen2.5-3b-classification-prompt-validation-v3" \
  >> "$KBA_LOG_DIR/full.log" 2>&1
printf '%s\n' "Validation generation and analysis complete."
