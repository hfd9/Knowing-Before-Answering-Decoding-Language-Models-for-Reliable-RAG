"""Offline rendering and environment preflight; no model weights are loaded."""
from importlib.metadata import version
import hashlib
import json
import platform
from pathlib import Path
import sys

import explanation_scope_metrics as metrics
import explanation_scope_runtime as scope


def main():
    runtime = scope.Runtime()
    source = runtime.reference['implementation_sha256']
    checked = {}
    for path, expected in source.items():
        actual = hashlib.sha256((scope.ROOT / path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('historical implementation fingerprint changed: ' + path)
        checked[path] = actual
    template = metrics.blank_review()
    if metrics.summarize(template)['reviewed_slots'] != 0:
        raise ValueError('unexpected reviewed endpoint')
    result = runtime.input_summary()
    result.update({'status': 'offline_runtime_preflight_not_collection_authorization',
                   'python': sys.version.split()[0], 'platform': platform.platform(),
                   'library_versions': {name: version(name) for name in
                                        ('torch', 'transformers', 'numpy', 'tokenizers', 'safetensors')},
                   'historical_implementation_sha256': checked,
                   'scoring_template_sha256': scope.digest_bytes(json.dumps(
                       template, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()),
                   'output_reviewed': 0, 'primary_point': None, 'formal_independent_approvals': 0,
                   'formal_gate': False, 'gpu_launch_ready': False,
                   'model_shards_hashed_in_this_process': False,
                   'gpu_inspected_in_this_process': False})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
