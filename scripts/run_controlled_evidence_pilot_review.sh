#!/bin/sh
# User launch:4 matched smoke inputs, then40 development inputs. Resume unchanged.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_FULL_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-controlled-evidence-pilot-v1"
KBA_SMOKE_DIR="$KBA_PROJECT_DIR/runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1"
KBA_LOG_DIR="$KBA_FULL_DIR/launch"
mkdir -p "$KBA_LOG_DIR"
printf '%s\n' "Running4-input technical smoke (free answers + fixed classification). Log: $KBA_LOG_DIR/smoke.log"
if sh "$KBA_PROJECT_DIR/scripts/run_controlled_evidence_pilot.sh" --smoke --run_dir "$KBA_SMOKE_DIR" >> "$KBA_LOG_DIR/smoke.log" 2>&1; then
  :
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "Controlled pilot smoke failed (exit $KBA_EXIT_CODE); full run was not started. Last log lines:" >&2
  tail -n 30 "$KBA_LOG_DIR/smoke.log" >&2
  exit "$KBA_EXIT_CODE"
fi
printf '%s\n' "Smoke passed. Running40 free answers +40 fixed classifications. Log: $KBA_LOG_DIR/full.log"
if sh "$KBA_PROJECT_DIR/scripts/run_controlled_evidence_pilot.sh" --run_dir "$KBA_FULL_DIR" >> "$KBA_LOG_DIR/full.log" 2>&1; then
  printf '%s\n' "Generation and probe analysis finished. Behavior requires explicit scoring; see reports/pilot.json and review/blind_review.html."
else
  KBA_EXIT_CODE=$?
  printf '%s\n' "Controlled pilot full run failed (exit $KBA_EXIT_CODE); repeat the same command to resume. Last log lines:" >&2
  tail -n 30 "$KBA_LOG_DIR/full.log" >&2
  exit "$KBA_EXIT_CODE"
fi
