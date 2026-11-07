"""User-run GPU preflight only: no model loading, generation, training or gate changes."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
import subprocess
import sys

import explanation_scope_e1 as e1
import explanation_scope_e1_intake as intake


def query(gpu_id, fields):
    return subprocess.run(['nvidia-smi', '-i', str(gpu_id), '--query-' + fields,
                           '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)


def inspect(gpu_id):
    if type(gpu_id) is not int or gpu_id < 0:
        raise ValueError('GPU index must be a nonnegative integer')
    intake.check_lock()
    info = query(gpu_id, 'gpu=index,uuid,name,memory.total,memory.used,driver_version')
    rows = list(csv.reader(info.stdout.splitlines(), skipinitialspace=True))
    if len(rows) != 1 or len(rows[0]) != 6:
        raise ValueError('nvidia-smi did not return exactly one GPU')
    index, uuid, name, total, used, driver = (value.strip() for value in rows[0])
    if index != str(gpu_id) or not uuid.startswith('GPU-'):
        raise ValueError('GPU index or UUID differs')
    active = query(gpu_id, 'compute-apps=pid,process_name,used_memory')
    processes = [line for line in active.stdout.splitlines() if line.strip()]
    result = {'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'gpu_index': gpu_id,
              'gpu_uuid': uuid, 'gpu_name': name, 'memory_total_mib': total, 'memory_used_mib': used,
              'driver_version': driver, 'active_compute_processes': processes,
              'formal_gate': False, 'gpu_launch_ready': False, 'collection_allowed': False,
              'model_loaded': False, 'model_inference': False, 'fit_performed': False,
              'gpu_is_exclusively_reserved': False}
    if processes:
        result.update({'status': 'busy_cuda_not_initialized', 'pytorch_cuda_checked': False,
                       'note': 'Compute processes were observed; do not start another GPU job.'})
        return result
    # Match the queried driver GPU by UUID, even if CUDA ordinal ordering differs.
    os.environ['CUDA_VISIBLE_DEVICES'] = uuid
    import torch
    available = torch.cuda.is_available()
    count = torch.cuda.device_count() if available else 0
    result.update({'status': 'gpu_device_snapshot_not_model_compatibility', 'pytorch_cuda_checked': True,
                   'torch_version': torch.__version__, 'torch_cuda_version': torch.version.cuda,
                   'cuda_available': available, 'visible_device_count': count,
                   'visible_device_name': torch.cuda.get_device_name(0) if available and count == 1 else None,
                   'bf16_supported': bool(torch.cuda.is_bf16_supported()) if available and count == 1 else None,
                   'note': 'Point-in-time observation only; no exclusive reservation or inference test.'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu-id', type=int, default=0, help='nvidia-smi GPU index (default: 0)')
    args = parser.parse_args()
    try:
        result = inspect(args.gpu_id)
    except (OSError, ValueError, subprocess.SubprocessError, ImportError, RuntimeError) as error:
        result = {'status': 'gpu_preflight_error', 'error_type': type(error).__name__, 'error': str(error),
                  'formal_gate': False, 'gpu_launch_ready': False, 'collection_allowed': False,
                  'model_loaded': False, 'model_inference': False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['status'] == 'busy_cuda_not_initialized' or result.get('cuda_available') is not True \
            or result.get('visible_device_count') != 1 or result.get('bf16_supported') is not True:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
