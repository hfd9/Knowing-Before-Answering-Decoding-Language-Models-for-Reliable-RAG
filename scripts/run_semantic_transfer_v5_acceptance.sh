#!/bin/sh
set -eu
KBA_ACCEPTANCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B "$KBA_ACCEPTANCE_DIR/scripts/semantic_transfer_v5_acceptance.py" "$@"
