#!/bin/sh
# Launch the frozen remaining-items pilot; GPU execution is performed by the user.
cd "$(dirname "$0")" || exit 1
CUDA_VISIBLE_DEVICES=0
export CUDA_VISIBLE_DEVICES
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_remaining_v2.py collect
