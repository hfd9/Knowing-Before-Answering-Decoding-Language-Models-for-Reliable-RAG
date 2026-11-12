#!/bin/sh
# User runs the remaining unattempted items; technical failures are saved, not retried.
cd "$(dirname "$0")" || exit 1
CUDA_VISIBLE_DEVICES=0
export CUDA_VISIBLE_DEVICES
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_unattempted_v5.py collect
