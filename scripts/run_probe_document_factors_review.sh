#!/bin/sh
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$KBA_PROJECT_DIR"
KBA_FACTORS_DIR=runs/qwen2.5-3b-probe-document-factors-v1
mkdir -p "$KBA_FACTORS_DIR/launch"
if ! sh scripts/run_probe_document_factors.sh --stage run --smoke --run_dir runs/qwen2.5-3b-probe-document-factors-smoke-v1 > "$KBA_FACTORS_DIR/launch/smoke.log" 2>&1; then
    tail -n 30 "$KBA_FACTORS_DIR/launch/smoke.log"
    exit 1
fi
if ! sh scripts/run_probe_document_factors.sh --stage run > "$KBA_FACTORS_DIR/launch/full.log" 2>&1; then
    tail -n 30 "$KBA_FACTORS_DIR/launch/full.log"
    exit 1
fi
tail -n 12 "$KBA_FACTORS_DIR/launch/full.log"
