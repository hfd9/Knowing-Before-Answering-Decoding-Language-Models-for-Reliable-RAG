#!/bin/sh
set -eu
KBA_TRANSFER_PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KBA_TRANSFER_PYTHON=${KBA_PYTHON:-/large_disk/wf/miniconda3/envs/kba-rag/bin/python}
exec "$KBA_TRANSFER_PYTHON" -B "$KBA_TRANSFER_PROJECT/scripts/semantic_transfer_materials_v2.py" "$@"
