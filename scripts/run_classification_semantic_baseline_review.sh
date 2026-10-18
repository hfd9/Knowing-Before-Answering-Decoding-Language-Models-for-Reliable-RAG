#!/bin/sh
# User launch: two candidates, each smoke9 then full285; repeat to resume.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_FULL_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-classification-semantic-v1"
KBA_SMOKE_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-classification-semantic-smoke-v1"
KBA_LOG_DIR="$KBA_FULL_DIR/launch"
mkdir -p "$KBA_LOG_DIR"
printf '%s\n' "Running two-candidate 9-item technical smoke; log: $KBA_LOG_DIR/smoke.log"
if sh "$KBA_PROJECT_DIR/scripts/run_classification_semantic_baseline.sh" \
    --limit_questions 3 --run_dir "$KBA_SMOKE_DIR" >> "$KBA_LOG_DIR/smoke.log" 2>&1; then
  :
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "Semantic baseline smoke failed (exit $KBA_EXIT_CODE); full run was not started. Last log lines:" >&2
  tail -n 30 "$KBA_LOG_DIR/smoke.log" >&2
  exit "$KBA_EXIT_CODE"
fi
printf '%s\n' "Both technical smoke gates passed. Running two x 285 validation items; log: $KBA_LOG_DIR/full.log"
if sh "$KBA_PROJECT_DIR/scripts/run_classification_semantic_baseline.sh" \
    --run_dir "$KBA_FULL_DIR" >> "$KBA_LOG_DIR/full.log" 2>&1; then
  printf '%s\n' "Validation generation and analysis finished. See reports/val.md; screening success is reported separately."
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "Semantic baseline full run failed (exit $KBA_EXIT_CODE); repeat the same launch command to resume. Last log lines:" >&2
  tail -n 30 "$KBA_LOG_DIR/full.log" >&2
  exit "$KBA_EXIT_CODE"
fi
