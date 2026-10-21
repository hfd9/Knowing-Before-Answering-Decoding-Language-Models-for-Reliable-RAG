#!/bin/sh
# User launch/resume: decoder prefill only, original48 inputs and sealed behavior.
set -eu
KBA_BIND_PROBE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_BIND_PROBE_ROOT/configs/local.env"
if [ "$#" -gt 0 ]; then
  exec "$KBA_PYTHON" -B "$KBA_BIND_PROBE_ROOT/scripts/behavior_binding_probe.py" "$@"
fi
KBA_BIND_PROBE_RUN="$KBA_BIND_PROBE_ROOT/runs/qwen2.5-3b-behavior-binding-probe-v1"
mkdir -p "$KBA_BIND_PROBE_RUN/launch"
printf '%s\n' "Frozen chat L28:48 original input prefills; no new answers or fitting." "Log: $KBA_BIND_PROBE_RUN/launch/prefill.log"
if "$KBA_PYTHON" -B "$KBA_BIND_PROBE_ROOT/scripts/behavior_binding_probe.py" --stage all >> "$KBA_BIND_PROBE_RUN/launch/prefill.log" 2>&1; then
  printf '%s\n' "48 prefills and descriptive joint analysis complete. Report: $KBA_BIND_PROBE_RUN/reports/joint.json" "Next: sh scripts/run_behavior_binding_probe.sh --stage verify-results"
else
  KBA_BIND_PROBE_EXIT=$?
  tail -n 35 "$KBA_BIND_PROBE_RUN/launch/prefill.log" >&2
  printf '%s\n' "Stopped. Normal interruption between committed rows can resume with this command. Uncommitted attempt, orphan feature or corruption requires inspection; do not remove markers or retry forwards." >&2
  exit "$KBA_BIND_PROBE_EXIT"
fi
