#!/bin/sh
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_PROJECT_DIR/configs/local.env"
exec "$KBA_PYTHON" -B "$KBA_PROJECT_DIR/scripts/probe_support_expression.py" "$@"
