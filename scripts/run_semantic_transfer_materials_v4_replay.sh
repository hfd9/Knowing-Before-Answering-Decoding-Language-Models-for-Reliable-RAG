#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python -B scripts/semantic_transfer_materials_v4_replay.py "$@"
