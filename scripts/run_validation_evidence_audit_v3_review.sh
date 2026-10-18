#!/bin/sh
# User launch: new v3 directories; retain the frozen 6/9 structure gate.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_RUN_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-validation-evidence-audit-v3"
KBA_SMOKE_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-validation-evidence-audit-smoke-v3"
KBA_LOG_DIR="$KBA_RUN_DIR/launch"
mkdir -p "$KBA_LOG_DIR"
printf '%s\n' "Running v3 9-item technical smoke; log: $KBA_LOG_DIR/smoke.log"
if sh "$KBA_PROJECT_DIR/scripts/run_validation_evidence_audit_v3.sh" \
  --limit_questions 3 --run_dir "$KBA_SMOKE_DIR" >> "$KBA_LOG_DIR/smoke.log" 2>&1; then
  :
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "V3 smoke generation failed (exit $KBA_EXIT_CODE). Last log lines:" >&2
  tail -n 25 "$KBA_LOG_DIR/smoke.log" >&2
  exit "$KBA_EXIT_CODE"
fi
if sh "$KBA_PROJECT_DIR/scripts/run_validation_evidence_audit_v3.sh" \
  --stage smoke-gate --limit_questions 3 --run_dir "$KBA_SMOKE_DIR" >> "$KBA_LOG_DIR/smoke.log" 2>&1; then
  :
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "V3 smoke gate failed (exit $KBA_EXIT_CODE); full run was not started. Last log lines:" >&2
  tail -n 25 "$KBA_LOG_DIR/smoke.log" >&2
  exit "$KBA_EXIT_CODE"
fi
printf '%s\n' "V3 technical smoke passed. Running 285 validation items; log: $KBA_LOG_DIR/full.log"
if sh "$KBA_PROJECT_DIR/scripts/run_validation_evidence_audit_v3.sh" \
  --run_dir "$KBA_RUN_DIR" >> "$KBA_LOG_DIR/full.log" 2>&1; then
  printf '%s\n' "V3 draft generation/diagnosis finished. Semantic review remains separate."
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "V3 full run failed (exit $KBA_EXIT_CODE). Rerun this command to resume. Last log lines:" >&2
  tail -n 25 "$KBA_LOG_DIR/full.log" >&2
  exit "$KBA_EXIT_CODE"
fi
