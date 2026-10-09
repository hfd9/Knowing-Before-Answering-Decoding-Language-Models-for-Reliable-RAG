#!/bin/sh
# Use the same offline model/environment as the hidden-state router.
set -eu
KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
. "$KBA_PROJECT_DIR/configs/local.env"
exec "$KBA_PYTHON" "$KBA_PROJECT_DIR/scripts/prompt_baseline.py" "$@"
