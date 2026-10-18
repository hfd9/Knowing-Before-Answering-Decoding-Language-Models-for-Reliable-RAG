#!/bin/sh
# CPU-only export. No model loading, GPU inference, or annotation import.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=/large_disk/wf/miniconda3/envs/kba-rag/bin/python
if [ ! -x "$KBA_PYTHON" ]; then
  KBA_PYTHON=python3
fi
exec "$KBA_PYTHON" -B "$KBA_PROJECT_DIR/scripts/validation_semantic_diagnosis.py" "$@"
