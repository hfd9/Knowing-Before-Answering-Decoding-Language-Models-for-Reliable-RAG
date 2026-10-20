#!/bin/sh
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B "$KBA_PROJECT_DIR/scripts/semantic_transfer_materials_v5.py" "$@"
