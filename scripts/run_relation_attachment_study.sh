#!/bin/sh
# User launch/resume; four technical smoke answers count within48.
set -eu
KBA_REL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_REL_ROOT/configs/local.env"
if [ "$#" -gt 0 ]; then
  exec "$KBA_PYTHON" -B "$KBA_REL_ROOT/scripts/relation_attachment_study.py" "$@"
fi
KBA_REL_RUN="$KBA_REL_ROOT/runs/qwen2.5-3b-relation-attachment-v1"
mkdir -p "$KBA_REL_RUN/launch"
printf '%s\n' "Relation attachment:48 inputs/six scenarios; four smoke included; no probe or fitting." "Log: $KBA_REL_RUN/launch/collection.log"
if "$KBA_PYTHON" -B "$KBA_REL_ROOT/scripts/relation_attachment_study.py" --stage all >> "$KBA_REL_RUN/launch/collection.log" 2>&1; then
  printf '%s\n' "All48 answers saved; behavior unreviewed. Summary: $KBA_REL_RUN/reports/collection.json"
else
  KBA_REL_EXIT=$?
  printf '%s\n' "Collection stopped (exit $KBA_REL_EXIT). Last log lines:" >&2
  tail -n 35 "$KBA_REL_RUN/launch/collection.log" >&2
  printf '%s\n' "Normal committed-prefix stops can resume with the same command. Uncommitted attempts or failed smoke require inspection; retain markers and do not re-answer." >&2
  exit "$KBA_REL_EXIT"
fi
