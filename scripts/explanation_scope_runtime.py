"""Offline real-tokenizer input/output verification and review packaging; no GPU collector."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))

import explanation_scope_ledger_simulator as plan_loader
import explanation_scope_metrics as metrics

BASE = ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2'
REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def text_sha(value):
    return digest_bytes(value.encode('utf-8'))


def ids_sha(ids):
    return text_sha(json.dumps(ids))


def json_sha(value):
    return text_sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def input_payload_sha(row):
    # Stable explicit framing, independent of metadata/condition.
    return text_sha(json.dumps({'question': row['question'], 'documents': row['documents']},
                               ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def smoke_digest(records):
    return digest_bytes(json.dumps(records[:4], ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':')).encode('utf-8'))


class Runtime:
    def __init__(self):
        from transformers import AutoTokenizer
        import evidence_experiment as renderer

        self.plan, self.plan_sha = plan_loader.load_plan()
        self.reference = json.loads(REFERENCE.read_text())
        self.model_dir = Path(self.reference['model'])
        if self.model_dir.name != 'Qwen2.5-3B-Instruct':
            raise ValueError('unexpected model directory')
        # Only small tokenizer/config files are read here, never weights or model inference.
        self.metadata_hashes = {}
        for name in ('config.json', 'model.safetensors.index.json', 'tokenizer.json',
                     'tokenizer_config.json', 'generation_config.json'):
            value = digest_bytes((self.model_dir / name).read_bytes())
            if value != self.reference['model_files_sha256'][name]:
                raise ValueError('model metadata fingerprint differs: ' + name)
            self.metadata_hashes[name] = value
        if renderer.FREE_INSTRUCTION != self.reference['instruction']:
            raise ValueError('free-answer instruction changed')
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
        self.vocab_size = len(self.tokenizer)
        self.renderer = renderer
        config = json.loads((self.model_dir / 'generation_config.json').read_text())
        eos = config['eos_token_id']
        self.eos_ids = eos if isinstance(eos, list) else [eos]
        if not self.eos_ids or any(type(t) is not int or t < 0 or t >= self.vocab_size for t in self.eos_ids):
            raise ValueError('invalid EOS configuration')
        rows = json.loads((BASE / 'materials.json').read_text())['items']
        self.rows = {row['id']: row for row in rows}
        if set(self.rows) != set(self.plan['ordered_ids']) or len(self.rows) != 48:
            raise ValueError('material grid/order mismatch')
        self.inputs = {item_id: self._render_input(item_id) for item_id in self.plan['ordered_ids']}

    def _render_input(self, item_id):
        row = self.rows[item_id]
        prompt = self.renderer.render_input({'question': row['question'], 'docs': row['documents']},
                                            'free_answer', 'chat', self.tokenizer)
        token_ids = self.renderer.encode(self.tokenizer, prompt, 'chat')['input_ids']
        if len(token_ids) + 128 > self.reference['context_tokens']:
            raise ValueError('input context overflow')
        if any(marker in prompt for marker in (item_id, 'local_repair_witnesses', 'alternative_target_values')):
            raise ValueError('coordinator metadata leaked into prompt')
        return {'input_sha256': input_payload_sha(row), 'prompt_sha256': text_sha(prompt),
                'input_token_ids_sha256': ids_sha(token_ids), 'input_tokens': len(token_ids)}

    def input_summary(self):
        values = list(self.inputs.values())
        return {'plan_sha256': self.plan_sha, 'items': [{'id': i, **self.inputs[i]} for i in self.plan['ordered_ids']],
                'eos_token_ids': self.eos_ids, 'tokenizer_vocab_size': self.vocab_size,
                'input_tokens_min': min(x['input_tokens'] for x in values),
                'input_tokens_max': max(x['input_tokens'] for x in values),
                'input_tokens_total': sum(x['input_tokens'] for x in values),
                'model_metadata_sha256': self.metadata_hashes,
                'weights_loaded': False, 'inference': False, 'collection_allowed': False}

    def generation_input(self, item_id):
        """Rebuild and check the exact prompt and token IDs a future collector would use."""
        if item_id not in self.inputs:
            raise ValueError('unknown material id')
        row = self.rows[item_id]
        prompt = self.renderer.render_input({'question': row['question'], 'docs': row['documents']},
                                            'free_answer', 'chat', self.tokenizer)
        token_ids = self.renderer.encode(self.tokenizer, prompt, 'chat')['input_ids']
        expected = self.inputs[item_id]
        if (input_payload_sha(row) != expected['input_sha256'] or text_sha(prompt) != expected['prompt_sha256']
                or ids_sha(token_ids) != expected['input_token_ids_sha256'] or len(token_ids) != expected['input_tokens']):
            raise ValueError('material or generation input changed since runtime initialization')
        return {'prompt': prompt, 'input_ids': token_ids}

    def make_record(self, index, generated_token_ids, elapsed_seconds, completed_at):
        if type(index) is not int or not 0 <= index < 48:
            raise ValueError('invalid record index')
        item_id = self.plan['ordered_ids'][index]
        if not isinstance(generated_token_ids, list) or not 1 <= len(generated_token_ids) <= 128:
            raise ValueError('invalid generated token count')
        if any(type(t) is not int or not 0 <= t < self.vocab_size for t in generated_token_ids):
            raise ValueError('invalid generated token id')
        if any(t in self.eos_ids for t in generated_token_ids[:-1]):
            raise ValueError('generated tokens after EOS')
        ended = generated_token_ids[-1] in self.eos_ids
        if not ended and len(generated_token_ids) != 128:
            raise ValueError('unexpected early stop without EOS')
        if type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError('invalid elapsed time')
        if not isinstance(completed_at, str):
            raise ValueError('completion time missing')
        try:
            timestamp = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
        except ValueError as error:
            raise ValueError('invalid completion time') from error
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError('completion time must include timezone')
        text = self.tokenizer.decode(generated_token_ids, skip_special_tokens=True)
        return {'index': index, 'id': item_id, 'plan_sha256': self.plan_sha, **self.inputs[item_id],
                'generated_token_ids': generated_token_ids, 'generated_tokens': len(generated_token_ids),
                'generated_token_ids_sha256': ids_sha(generated_token_ids),
                'raw_output': text, 'raw_output_sha256': text_sha(text),
                'ended_with_eos': ended, 'hit_output_limit': len(generated_token_ids) == 128 and not ended,
                'elapsed_seconds': elapsed_seconds, 'completed_at': completed_at}

    def validate_record(self, record, index):
        if not isinstance(record, dict) or type(index) is not int or not 0 <= index < 48:
            raise ValueError('invalid record')
        if type(record.get('index')) is not int or any(type(record.get(k)) is not int for k in ('input_tokens', 'generated_tokens')):
            raise ValueError('invalid record count types')
        if any(type(record.get(k)) is not bool for k in ('ended_with_eos', 'hit_output_limit')):
            raise ValueError('invalid record stop flag types')
        expected = self.make_record(index, record.get('generated_token_ids'),
                                    record.get('elapsed_seconds'), record.get('completed_at'))
        if record != expected:
            raise ValueError('record input, output, ordering or stop fields differ')
        return expected

    def validate_cache(self, attempts, records, smoke=None, failure=None, pending_files=()):
        """Check declared data and token bytes, not actual disk atomicity or model origin."""
        if pending_files:
            raise ValueError('uncommitted temporary files must be preserved and inspected')
        if failure is not None:
            raise ValueError('recorded failure must be inspected')
        if not isinstance(attempts, list) or not isinstance(records, list) or len(records) > 48:
            raise ValueError('invalid attempt or record list')
        if len(attempts) != len(records):
            raise ValueError('uncommitted attempt or orphan record; do not regenerate')
        for i, (attempt, record) in enumerate(zip(attempts, records)):
            if not isinstance(attempt, dict) or type(attempt.get('index')) is not int or attempt != {'index': i, 'id': self.plan['ordered_ids'][i], 'plan_sha256': self.plan_sha}:
                raise ValueError('attempt order or binding mismatch')
            self.validate_record(record, i)
        state = 'validated_prefix'
        if len(records) >= 4:
            if smoke is None:
                state = 'awaiting_technical_smoke'
            else:
                if not isinstance(smoke, dict) or type(smoke.get('passed')) is not bool or type(smoke.get('semantic_correctness_assessed')) is not bool:
                    raise ValueError('invalid smoke receipt types')
                expected = self.make_smoke_receipt(records)
                if smoke != expected:
                    raise ValueError('smoke receipt or record binding differs')
                if not smoke['passed']:
                    state = 'blocked_failed_smoke'
        elif smoke is not None:
            raise ValueError('smoke receipt before four records')
        if len(records) > 4 and state != 'validated_prefix':
            raise ValueError('records after failed or missing smoke')
        if len(records) == 48 and state == 'validated_prefix':
            state = 'validated_complete_unreviewed'
        return {'state': state, 'records': len(records), 'collection_allowed': False,
                'gpu_launch_ready': False, 'does_not_establish_output_origin': True}

    def make_smoke_receipt(self, records):
        if len(records) < 4:
            raise ValueError('four records required for smoke')
        for i in range(4):
            self.validate_record(records[i], i)
        passed = all(r['raw_output'].strip() and r['ended_with_eos'] and not r['hit_output_limit']
                     for r in records[:4])
        return {'plan_sha256': self.plan_sha, 'records_sha256': smoke_digest(records),
                'passed': bool(passed), 'semantic_correctness_assessed': False}

    def review_artifacts(self, attempts, records, smoke):
        check = self.validate_cache(attempts, records, smoke)
        if check['state'] != 'validated_complete_unreviewed':
            raise ValueError('full validated 48 records required')
        by_id = {r['id']: r for r in records}
        ordered = sorted(self.rows, key=lambda x: text_sha('scope-output-review-v1|' + x))
        mapping = {f'R{i:03d}': item_id for i, item_id in enumerate(ordered, 1)}
        items = []
        reverse = {}
        for review_id, item_id in mapping.items():
            row, record = self.rows[item_id], by_id[item_id]
            items.append({'item_id': review_id, 'question': row['question'],
                          'documents': row['documents'], 'answer': record['raw_output']})
            reverse[item_id] = review_id
        review = metrics.blank_review()
        for row in review['rows']:
            item_id = f"exs{row['scene']:02d}_{row['condition']}"
            record = by_id[item_id]
            row['source_item_id'] = reverse[item_id]
            row['input_sha256'] = record['input_sha256']
            row['output_sha256'] = record['raw_output_sha256']
            row['technical_status'] = ('empty' if not record['raw_output'].strip() else
                                       'truncated' if record['hit_output_limit'] else 'complete')
        metrics.validate(review)
        packet = {'items': items}
        return {'packet': packet, 'coordinator_mapping': mapping,
                'endpoint_template': review,
                'artifact_sha256': {'packet': json_sha(packet), 'coordinator_mapping': json_sha(mapping),
                                    'endpoint_template': json_sha(review)},
                'artifact_hash_method': 'UTF-8 JSON ensure_ascii=false sort_keys=true separators=comma-colon',
                'warning': 'Mapping and endpoint template expose conditions; keep separate from packet. '
                           'No semantic scores or independence approval.'}

    def assert_collection_disabled(self):
        if self.plan['guards']['collection_allowed'] is not False or self.plan['guards']['gpu_launch_ready'] is not False:
            raise ValueError('unexpected changed collection guard')
        raise PermissionError('collection and GPU are disabled by the bound draft plan')
