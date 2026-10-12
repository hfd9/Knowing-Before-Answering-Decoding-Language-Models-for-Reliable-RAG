#!/bin/sh
# Sequential smoke and full run of the existing frozen classification protocol.
set -eu
KBA_REVIEW_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$KBA_REVIEW_ROOT"
KBA_REVIEW_GPU_PIDS=$(nvidia-smi --id=0 --query-compute-apps=pid --format=csv,noheader,nounits)
if [ -n "$KBA_REVIEW_GPU_PIDS" ]; then
    echo 'GPU 0 has an active compute process; leaving experiments untouched.' >&2
    exit 1
fi
KBA_REVIEW_LOG_DIR=runs/qwen2.5-3b-classification-grid/launch-2026-10-11
mkdir -p "$KBA_REVIEW_LOG_DIR"
echo "Smoke log: $KBA_REVIEW_LOG_DIR/smoke.log"
if ! sh scripts/run_classification_grid.sh --limit_questions 3 --run_dir runs/qwen2.5-3b-classification-grid-smoke > "$KBA_REVIEW_LOG_DIR/smoke.log" 2>&1; then
    tail -n 30 "$KBA_REVIEW_LOG_DIR/smoke.log" >&2
    exit 1
fi
echo "Smoke passed. Full run log: $KBA_REVIEW_LOG_DIR/full.log"
if ! sh scripts/run_classification_grid.sh > "$KBA_REVIEW_LOG_DIR/full.log" 2>&1; then
    tail -n 30 "$KBA_REVIEW_LOG_DIR/full.log" >&2
    exit 1
fi
echo 'Full classification inference and analysis completed.'
