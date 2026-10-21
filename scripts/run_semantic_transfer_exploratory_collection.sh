#!/bin/sh
# User launch/resume: smoke is the first4 of the same240 inputs; no extra GPU outputs.
set -eu
KBA_EXPLORE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_EXPLORE_DIR/configs/local.env"
if [ "$#" -gt 0 ]; then
  exec "$KBA_PYTHON" -B "$KBA_EXPLORE_DIR/scripts/semantic_transfer_exploratory_collection.py" "$@"
fi
KBA_EXPLORE_RUN="$KBA_EXPLORE_DIR/runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1"
mkdir -p "$KBA_EXPLORE_RUN/launch"
printf '%s\n' "Exploratory collection:4 technical smoke inputs followed by236 remaining inputs; no new probe training." "Log: $KBA_EXPLORE_RUN/launch/collection.log"
if "$KBA_PYTHON" -B "$KBA_EXPLORE_DIR/scripts/semantic_transfer_exploratory_collection.py" --stage all >> "$KBA_EXPLORE_RUN/launch/collection.log" 2>&1; then
  printf '%s\n' "All240 exploratory answers/readouts saved and verified. Summary: $KBA_EXPLORE_RUN/reports/collection.json"
else
  KBA_EXPLORE_EXIT=$?
  printf '%s\n' "Collection stopped (exit $KBA_EXPLORE_EXIT). Existing outputs are preserved. Last log lines:" >&2
  tail -n 35 "$KBA_EXPLORE_RUN/launch/collection.log" >&2
  printf '%s\n' "If stopped before generation or between committed inputs, repeat this command to resume. An uncommitted attempt or failed technical smoke requires inspection; do not delete markers or force regeneration." >&2
  exit "$KBA_EXPLORE_EXIT"
fi
