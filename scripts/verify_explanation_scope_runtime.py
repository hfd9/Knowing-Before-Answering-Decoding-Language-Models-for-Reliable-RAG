"""Independently assemble P0/chat inputs; no import of the runtime verifier or model."""
import hashlib
import json
from pathlib import Path
import sys

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from prompts import render_prompt  # noqa: E402

MATERIALS = ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2/materials.json'
PLAN = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/execution-draft.json'
REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
PREVIEW = ROOT / 'docs/review/2026-11-06-explanation-scope-runtime-preflight-v1/input-fingerprints.json'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    rows = {r['id']: r for r in json.loads(MATERIALS.read_text())['items']}
    plan, reference = json.loads(PLAN.read_text()), json.loads(REFERENCE.read_text())
    result = json.loads(PREVIEW.read_text())
    expected = {r['id']: r for r in result['items']}
    assert len(rows) == len(expected) == len(plan['ordered_ids']) == 48
    assert set(rows) == set(expected) == set(plan['ordered_ids'])
    assert result['plan_sha256'] == sha(PLAN.read_bytes())
    tokenizer = AutoTokenizer.from_pretrained(reference['model'], local_files_only=True)
    matches = 0
    for item_id in plan['ordered_ids']:
        row = rows[item_id]
        body = render_prompt('P0', row['question'], row['documents'], instruction='')
        prompt = tokenizer.apply_chat_template([
            {'role': 'system', 'content': reference['instruction']},
            {'role': 'user', 'content': body}], tokenize=False, add_generation_prompt=True)
        token_ids = tokenizer(prompt, truncation=False, add_special_tokens=False)['input_ids']
        payload = json.dumps({'question': row['question'], 'documents': row['documents']},
                             ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        computed = {'id': item_id, 'input_sha256': sha(payload), 'prompt_sha256': sha(prompt.encode()),
                    'input_token_ids_sha256': sha(json.dumps(token_ids).encode()), 'input_tokens': len(token_ids)}
        assert computed == expected[item_id], item_id
        matches += 1
    print(json.dumps({'status': 'independent_chat_assembly_matches_shared_prompt_builder',
                      'verified_items': matches, 'plan_sha256': sha(PLAN.read_bytes()),
                      'input_fingerprints_sha256': sha(PREVIEW.read_bytes()),
                      'shared_dependencies': ['P0 render_prompt', 'local tokenizer', 'reference instruction'],
                      'model_weights_loaded': False, 'model_inference': False,
                      'independent_semantic_approval': False, 'gpu_launch_ready': False}, indent=2))


if __name__ == '__main__':
    main()
