#!/bin/sh
# User executes the 127 unattempted items; failures stay saved and stop collection.
cd "$(dirname "$0")" || exit 1
CUDA_VISIBLE_DEVICES=0
export CUDA_VISIBLE_DEVICES
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_unattempted_v4.py collect
