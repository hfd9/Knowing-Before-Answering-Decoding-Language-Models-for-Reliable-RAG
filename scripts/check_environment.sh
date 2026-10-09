#!/bin/sh
# Run from any working directory; Conda activation is not required.
set -eu

KBA_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}

if [ ! -x "$KBA_PYTHON" ]; then
    printf 'Cannot find the kba-rag Python interpreter: %s\n' "$KBA_PYTHON" >&2
    exit 1
fi

. "$KBA_PROJECT_DIR/configs/local.env"
exec "$KBA_PYTHON" "$KBA_PROJECT_DIR/scripts/check_environment.py" "$@"
