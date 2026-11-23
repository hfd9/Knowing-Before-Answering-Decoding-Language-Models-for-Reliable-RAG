#!/bin/sh
set -eu
cd "$(dirname "$0")"
pilot_python=/large_disk/wf/miniconda3/envs/kba-rag/bin/python
pilot_run="$(pwd -P)/runs/qwen2.5-3b-query-determinacy-shared-pilot-v1"
if [ ! -e "$pilot_run" ] && [ ! -L "$pilot_run" ]; then
    "$pilot_python" scripts/query_determinacy_shared_live.py prepare "$pilot_run" --user-executed
fi
exec "$pilot_python" scripts/query_determinacy_shared_live.py collect "$pilot_run" --user-executed
