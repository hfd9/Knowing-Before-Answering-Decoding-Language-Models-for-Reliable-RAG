#!/bin/sh
# User launch/resume: 4 technical smoke answers are included in the total48.
set -eu
KBA_BIND_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_BIND_ROOT/configs/local.env"
if [ "$#" -gt 0 ]; then
  exec "$KBA_PYTHON" -B "$KBA_BIND_ROOT/scripts/behavior_binding_study.py" "$@"
fi
KBA_BIND_RUN="$KBA_BIND_ROOT/runs/qwen2.5-3b-behavior-binding-v1"
mkdir -p "$KBA_BIND_RUN/launch"
printf '%s\n' "Behavior binding:48 fixed fictional inputs;4 smoke included; no probe or training." "Log: $KBA_BIND_RUN/launch/collection.log"
if "$KBA_PYTHON" -B "$KBA_BIND_ROOT/scripts/behavior_binding_study.py" --stage all >> "$KBA_BIND_RUN/launch/collection.log" 2>&1; then
  printf '%s\n' "All48 answers collected. Behavior review is still pending. Summary: $KBA_BIND_RUN/reports/collection.json"
else
  KBA_BIND_EXIT=$?
  printf '%s\n' "Collection stopped (exit $KBA_BIND_EXIT). Last log lines:" >&2
  tail -n 35 "$KBA_BIND_RUN/launch/collection.log" >&2
  printf '%s\n' "Resume with the same command only after a normal stop between committed inputs. Uncommitted attempts or failed smoke require inspection; do not delete markers or re-answer." >&2
  exit "$KBA_BIND_EXIT"
fi
