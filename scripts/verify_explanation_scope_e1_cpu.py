"""Read-only E1 source, dependency and model-file fingerprint check; never touches CUDA."""
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import sys
import time

import explanation_scope_e1 as e1
import explanation_scope_e1_intake as intake
import explanation_scope_ledger_simulator as ledger
import explanation_scope_runtime as scope


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify():
    started = time.monotonic()
    intake.check_lock()
    plan, plan_sha = ledger.load_plan()
    claim_path = e1.ROOT / 'docs/review/2026-11-07-explanation-scope-e1/claim-intake-snapshot.json'
    claim_snapshot = json.loads(claim_path.read_text(encoding='utf-8'))
    for name, expected in claim_snapshot['files_sha256'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or file_sha(e1.ROOT / path) != expected:
            raise ValueError('Claim-intake source hash changed: ' + name)
    if claim_snapshot['formal_gate'] is not False or claim_snapshot['gpu_launch_ready'] is not False:
        raise ValueError('Claim-intake snapshot unexpectedly enables a gate')
    reference = json.loads(scope.REFERENCE.read_text(encoding='utf-8'))
    files = reference['model_files_sha256']
    expected_names = {'config.json', 'model.safetensors.index.json', 'tokenizer.json',
                      'tokenizer_config.json', 'generation_config.json',
                      'model-00001-of-00002.safetensors', 'model-00002-of-00002.safetensors'}
    if set(files) != expected_names:
        raise ValueError('Model inventory changed')
    model = Path(reference['model'])
    if model.name != 'Qwen2.5-3B-Instruct' or not model.is_dir():
        raise ValueError('Expected local Qwen2.5-3B-Instruct directory is missing')
    checks = []
    for name in sorted(files):
        path = model / name
        actual = file_sha(path)
        checks.append({'name': name, 'bytes': path.stat().st_size, 'sha256': actual,
                       'matches_reference': actual == files[name]})
    packages = {}
    for name in ('torch', 'transformers', 'accelerate', 'safetensors', 'tokenizers'):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    result = {'status': 'cpu_source_and_file_hash_check_not_gpu_or_model_compatibility',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.executable,
        'python_version': sys.version.split()[0], 'packages': packages, 'model_dir': str(model),
        'model_files': checks, 'all_model_files_match': all(row['matches_reference'] for row in checks),
        'e1_protocol_sha256': e1.PROTOCOL_SHA256, 'source_plan_sha256': plan_sha,
        'e1_lock_sha256': file_sha(e1.IMPLEMENTATION_LOCK), 'claim_snapshot_sha256': file_sha(claim_path),
        'claim_sources_checked': len(claim_snapshot['files_sha256']),
        'e1_real_run_exists': e1.E1_RUN.exists(), 'original_scope_run_exists':
            (e1.ROOT / 'runs/qwen2.5-3b-explanation-scope-v1').exists(),
        'formal_gate': False, 'gpu_launch_ready': False, 'fit_budget': 0,
        'held_out_380_accessed': False, 'model_weights_loaded': False,
        'model_inference': False, 'cuda_queried': False, 'gpu_readiness_proved': False,
        'elapsed_seconds': round(time.monotonic() - started, 3)}
    return result


def main():
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['all_model_files_match']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
