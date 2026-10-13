#!/bin/sh
# User launch: technical smoke, then the complete val-only evidence diagnosis.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_LOG_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-validation-evidence-audit-v1/launch"
mkdir -p "$KBA_LOG_DIR"
printf '%s\n' "Running 9-item technical smoke; log: $KBA_LOG_DIR/smoke.log"
sh "$KBA_PROJECT_DIR/scripts/run_validation_evidence_audit.sh" \
  --limit_questions 3 \
  --run_dir "$KBA_PROJECT_DIR/runs/qwen2.5-3b-validation-evidence-audit-smoke-v1" \
  >> "$KBA_LOG_DIR/smoke.log" 2>&1
sh "$KBA_PROJECT_DIR/scripts/run_validation_evidence_audit.sh" \
  --stage smoke-gate --limit_questions 3 \
  --run_dir "$KBA_PROJECT_DIR/runs/qwen2.5-3b-validation-evidence-audit-smoke-v1" \
  >> "$KBA_LOG_DIR/smoke.log" 2>&1
printf '%s\n' "Technical smoke finished. Running all 285 validation items; log: $KBA_LOG_DIR/full.log"
sh "$KBA_PROJECT_DIR/scripts/run_validation_evidence_audit.sh" \
  --run_dir "$KBA_PROJECT_DIR/runs/qwen2.5-3b-validation-evidence-audit-v1" \
  >> "$KBA_LOG_DIR/full.log" 2>&1
printf '%s\n' "Draft generation and diagnosis finished; semantic review is a separate step."
