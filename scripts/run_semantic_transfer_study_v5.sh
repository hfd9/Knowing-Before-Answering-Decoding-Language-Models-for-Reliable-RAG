#!/bin/sh
set -eu
KBA_STUDY_V5_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_STUDY_V5_DIR/configs/local.env"
exec "$KBA_PYTHON" -B "$KBA_STUDY_V5_DIR/scripts/semantic_transfer_study_v5.py" "$@"
