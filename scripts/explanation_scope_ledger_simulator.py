"""CPU-only synthetic ledger checks; this is not a collector or a real cache verifier."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/execution-draft.json'
HEX = re.compile(r'[0-9a-f]{64}\Z')


def load_plan():
    raw = PLAN_PATH.read_bytes()
    plan = json.loads(raw)
    required = {
        'docs/review/2026-11-06-explanation-scope-materials-v2/design-lock.json',
        'docs/review/2026-11-06-explanation-scope-materials-v2/materials.json',
        'docs/review/2026-11-06-explanation-scope-materials-v2/input-packet.json',
        'docs/review/2026-11-06-explanation-scope-materials-v2/coordinator.json',
        'docs/review/2026-11-06-explanation-scope-materials-v2/author-interpretation.json',
        'docs/review/2026-11-06-explanation-scope-materials-v2/preflight.json',
        'prompts/explanation_evidence_scope_draft_v1.json',
        'prompts/explanation_scope_scoring_contract_v1.json',
        'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json',
    }
    if set(plan['source_sha256']) != required:
        raise ValueError('bound source list differs')
    for path, expected in plan['source_sha256'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError('bound input changed: ' + path)
    ids, smoke = plan['ordered_ids'], plan['smoke_ids']
    expected_smoke = [f'exs01_{condition}' for condition in ('S', 'I0', 'IU', 'CT')]
    materials = json.loads((ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2/materials.json').read_text())['items']
    material_ids = [row['id'] for row in materials]
    expected_order = expected_smoke + sorted((x for x in material_ids if x not in expected_smoke),
        key=lambda x: hashlib.sha256(('explanation-scope-order-v1|' + x).encode()).hexdigest())
    if len(ids) != 48 or len(set(ids)) != 48 or smoke != expected_smoke or ids != expected_order:
        raise ValueError('invalid frozen draft order')
    if plan['guards'] != {'semantic_independent_approvals': 0, 'formal_gate': False,
                          'gpu_launch_ready': False, 'collection_allowed': False,
                          'held_out_380_accessed': False, 'fit_budget': 0}:
        raise ValueError('draft must not enable collection or GPU')
    return plan, hashlib.sha256(raw).hexdigest()


def smoke_digest(records):
    raw = json.dumps(records[:4], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def evaluate(ledger, plan, plan_hash):
    """Evaluate declared synthetic metadata, not real outputs or filesystem atomicity."""
    if ledger.get('synthetic') is not True or ledger.get('plan_sha256') != plan_hash:
        raise ValueError('synthetic ledger and exact plan binding required')
    attempts, records = ledger.get('attempts'), ledger.get('records')
    if not isinstance(attempts, list) or not isinstance(records, list):
        raise ValueError('attempts and records must be lists')
    ids = plan['ordered_ids']
    if len(records) > 48 or len(attempts) not in (len(records), len(records) + 1) or len(attempts) > 48:
        raise ValueError('invalid marker/record counts')
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict) or type(attempt.get('index')) is not int or attempt != {'index': index, 'id': ids[index], 'plan_sha256': plan_hash}:
            raise ValueError('attempt is not a bound ordered prefix')
    for index, record in enumerate(records):
        if not isinstance(record, dict) or type(record.get('index')) is not int or record.get('index') != index or record.get('id') != ids[index] or record.get('plan_sha256') != plan_hash:
            raise ValueError('record is not a bound ordered prefix')
        if not all(isinstance(record.get(k), str) and HEX.fullmatch(record[k]) for k in ('prompt_sha256', 'output_sha256')):
            raise ValueError('invalid hash declaration')
        n = record.get('output_tokens')
        eos, limit, nonempty = (record.get(k) for k in ('ended_with_eos', 'hit_output_limit', 'nonempty_output'))
        if type(n) is not int or not 1 <= n <= 128 or any(type(x) is not bool for x in (eos, limit, nonempty)):
            raise ValueError('invalid synthetic output metadata')
        if limit != (n == 128 and not eos) or not (eos or limit):
            raise ValueError('inconsistent EOS/output limit')
    smoke = ledger.get('smoke')
    if smoke is not None:
        if len(records) < 4 or not isinstance(smoke, dict) or type(smoke.get('passed')) is not bool:
            raise ValueError('invalid smoke receipt')
        if smoke.get('plan_sha256') != plan_hash or smoke.get('records_sha256') != smoke_digest(records):
            raise ValueError('smoke receipt does not bind first four records')
        technical_pass = all(r['nonempty_output'] and r['ended_with_eos'] and not r['hit_output_limit'] for r in records[:4])
        if smoke['passed'] != technical_pass:
            raise ValueError('smoke receipt contradicts technical metadata')
    failure = ledger.get('failure')
    if failure is not None and (not isinstance(failure, dict) or not isinstance(failure.get('reason'), str) or not failure['reason'].strip()):
        raise ValueError('failure must have a reason')
    if failure is not None:
        state = 'blocked_recorded_failure'
    elif len(attempts) > len(records):
        state = 'blocked_uncommitted_attempt'
    elif len(records) >= 4 and smoke is None:
        state = 'blocked_missing_smoke_receipt'
    elif smoke is not None and not smoke['passed']:
        state = 'blocked_failed_smoke'
    elif len(records) == 48:
        state = 'synthetic_complete'
    else:
        state = 'synthetic_clean_prefix'
    return {'state': state, 'declared_attempts': len(attempts), 'declared_records': len(records),
            'ledger_next_step_unblocked': state == 'synthetic_clean_prefix',
            'collection_permitted': False, 'gpu_launch_ready': False,
            'scope': 'synthetic_metadata_only_no_filesystem_atomicity_no_output_decode'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('verify', 'simulate'), required=True)
    parser.add_argument('--fixture', type=Path)
    args = parser.parse_args()
    plan, plan_hash = load_plan()
    if args.stage == 'simulate':
        if args.fixture is None:
            parser.error('--fixture is required for simulate')
        ledger = json.loads(args.fixture.read_text())
    else:
        if args.fixture is not None:
            parser.error('--fixture is only for simulate')
        ledger = {'synthetic': True, 'plan_sha256': plan_hash, 'attempts': [], 'records': [],
                  'smoke': None, 'failure': None}
    print(json.dumps(evaluate(ledger, plan, plan_hash), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
