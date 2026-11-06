"""Stream hashes of the frozen local model files; do not load model weights."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'


def main():
    reference = json.loads(REFERENCE.read_text())
    model = Path(reference['model'])
    if model.name != 'Qwen2.5-3B-Instruct':
        raise ValueError('unexpected model')
    entries = []
    started = time.monotonic()
    for name, expected in reference['model_files_sha256'].items():
        if Path(name).name != name:
            raise ValueError('invalid model file name')
        path = model / name
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
        entries.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest(),
                        'expected_sha256': expected, 'matches_recorded': digest.hexdigest() == expected})
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'model': str(model),
              'files': entries, 'all_match': all(x['matches_recorded'] for x in entries),
              'elapsed_seconds': round(time.monotonic() - started, 3),
              'weights_loaded': False, 'inference': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['all_match']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
