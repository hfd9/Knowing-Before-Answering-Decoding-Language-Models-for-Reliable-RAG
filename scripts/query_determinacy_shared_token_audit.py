#!/usr/bin/env python3
"""CPU-only tokenizer check using author references as simulated extraction outputs."""
import json
from pathlib import Path
import query_determinacy_shared_live as live

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1'


def audit():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(live.MODEL), local_files_only=True)
    pr, rr = (BASE/'public-12-v2.json').read_bytes(), (BASE/'reference-12-v2.json').read_bytes()
    public, reference = json.loads(pr), json.loads(rr)
    items = []
    for c, q, kind, branch in live.slots(public):
        values = [w['value'] for w in reference['cases'][c['id']]['worlds']]
        text = live.prompt(kind, c, q, values, branch)
        rendered = tok.apply_chat_template([{'role': 'user', 'content': text}], tokenize=False, add_generation_prompt=True)
        ids = tok(rendered, add_special_tokens=False, truncation=False)['input_ids']
        items.append({'case': c['id'], 'question': q['id'] if q else None, 'kind': kind, 'branch': branch,
                      'input_tokens': len(ids), 'prompt_sha256': live.sha(text.encode()),
                      'rendered_sha256': live.sha(rendered.encode()), 'token_ids_sha256': live.sha(live.encode(ids))})
    snapshot = json.loads(live.MODEL_REFERENCE.read_bytes())
    return {'schema': 'shared_token_audit_v1', 'public_sha256': live.sha(pr), 'author_reference_sha256': live.sha(rr),
            'runner_sha256': live.hash_file(Path(live.__file__)), 'count': len(items),
            'min_tokens': min(i['input_tokens'] for i in items), 'max_tokens': max(i['input_tokens'] for i in items),
            'max_new_tokens': live.MAX_NEW_TOKENS, 'context_limit': snapshot['context_tokens'],
            'all_within_context': all(i['input_tokens'] + live.MAX_NEW_TOKENS <= snapshot['context_tokens'] for i in items),
            'note': 'CPU tokenizer only; author reference values simulate predictions, real predictions may differ; no model/GPU.',
            'items': items}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))
