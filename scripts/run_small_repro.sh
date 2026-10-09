#!/bin/sh
# Run the small hidden-state experiment from any working directory.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_PROJECT_DIR/configs/local.env"
exec "$KBA_PYTHON" "$KBA_PROJECT_DIR/scripts/small_repro.py" "$@"
