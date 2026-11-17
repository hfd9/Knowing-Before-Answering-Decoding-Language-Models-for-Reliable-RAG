#!/bin/sh
set -eu
cd "$(dirname "$0")"
export CUDA_VISIBLE_DEVICES=0
exec /large_disk/wf/miniconda3/envs/kba-rag/bin/python scripts/query_determinacy_paraphrase_run.py collect
