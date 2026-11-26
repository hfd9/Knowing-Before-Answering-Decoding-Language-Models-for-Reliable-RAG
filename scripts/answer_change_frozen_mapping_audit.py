"""Losslessly map exposed frozen-system and 7B outputs without scoring them."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'docs/review/2026-11-25-role-assignment-holdout-v1'
NEW = ROOT / 'docs/review/2026-11-25-answer-change-7b-development-v1'
NEW_ZIP = ROOT / 'docs/review/2026-11-25-answer-change-7b-results-v1/raw.zip'
OUT = ROOT / 'docs/review/2026-11-26-frozen-mapping-audit-v1/mapping.json'
CASES = ('ssa-S0', 'ssa-D0', 'spouse-S0', 'spouse-D0')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def map_candidate(case, candidate):
    """Keep source intact; do not turn program errors into model abstentions."""
    require(isinstance(candidate, dict), 'candidate must be object')
    outcome, error = candidate['outcome'], candidate['error']
    require(not (outcome is not None and error is not None), 'conflicting result and error')
    if outcome is None:
        require(isinstance(error, str) and error, 'missing error')
        view = {'availability': 'pipeline_error', 'error': error, 'structured_action': None,
                'structured_branches': None, 'ask_event': None}
    else:
        require(isinstance(outcome, dict), 'invalid outcome')
        require(candidate['tag'] == outcome['tag'], 'tag mismatch')
        require(outcome['tag'] in ('ANSWER_Y', 'ANSWER_N', 'ASK_DATE', 'UNRESOLVED'), 'unknown action')
        view = {'availability': 'structured_result', 'error': None,
                'structured_action': outcome['tag'], 'structured_branches': outcome['branches'],
                'ask_event': outcome['ask_event']}
    return {'case': case, 'route': 'frozen_3b', 'format': 'structured', 'view': view,
            'original_candidate': candidate}


def map_text(task, record):
    require(task['id'] == record['id'], 'text task mismatch')
    require(record['status'] in ('complete', 'truncated', 'empty', 'unexpected_stop'), 'unknown status')
    require(isinstance(record['output'], str), 'output must be string')
    return {'case': task['case'], 'route': '7b_' + task['route'], 'format': 'text',
            'view': {'availability': 'text_record', 'generation_status': record['status'],
                     'text': record['output']}, 'original_task': task, 'original_record': record}


def audit_input(public, task):
    cases = {row['id']: row for row in public['cases']}
    case = cases[task['case']]
    profile = public['profiles'][case['profile']]
    text = task['messages'][1]['content']
    require(profile['question'] in text and case['facts'] in text, 'question or facts differ')
    require(all(f'[{tag}] {value}' in text for tag, value in profile['evidence'].items()),
            'evidence differs')
    claims = profile['scope_claims']
    heading = f'Author-prepared scope statements (derived from [{claims["source"]}]):'
    require(heading in text and all(item['statement'] in text for item in claims['claims']),
            'scope annotation differs')
    return {'question_facts_evidence_match': True, 'scope_source_disclosed_to_7b': claims['source'],
            'scope_statement_count': len(claims['claims'])}


def build():
    public = json.loads((OLD / 'public.json').read_text())
    results = json.loads((OLD / 'results.json').read_text())
    plan = json.loads((NEW / 'plan.json').read_text())
    require(len(plan) == 8 and {x['case'] for x in plan} == set(CASES), 'unexpected 7b plan')
    rows = [map_candidate(case, results['cases'][case]['candidate']) for case in CASES]
    input_audit = {}
    with ZipFile(NEW_ZIP) as archive:
        seal = json.loads(archive.read('run/seal.json'))
        names = {name for name in archive.namelist() if name.startswith('run/')}
        require(names == {'run/' + n for n in seal} | {'run/seal.json'}, '7b archive file set differs')
        require(all(hashlib.sha256(archive.read('run/' + name)).hexdigest() == digest
                    for name, digest in seal.items()), '7b archive seal mismatch')
        require(archive.read('prepared/plan.json') == (NEW / 'plan.json').read_bytes(), 'plan archive differs')
        for i, task in enumerate(plan):
            attempt = json.loads(archive.read(f'run/{i:02d}.attempt.json'))
            record = json.loads(archive.read(f'run/{i:02d}.record.json'))
            require(attempt['task'] == task, 'archive attempt differs')
            input_audit[task['id']] = audit_input(public, task)
            rows.append(map_text(task, record))
    require(len(rows) == 12, 'unexpected row count')
    return {'purpose': 'exposed development output mapping, not scored',
            'sources_sha256': {str(path.relative_to(ROOT)): sha(path) for path in
                               (OLD / 'public.json', OLD / 'results.json', OLD / 'raw.zip',
                                OLD / 'freeze.json', NEW / 'plan.json', NEW_ZIP, Path(__file__))},
            'input_audit': input_audit, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = encode(build())
    if args.verify:
        require(OUT.read_bytes() == result, 'mapping differs')
        print('Mapping replay passed.')
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open('xb') as stream:
            stream.write(result)
        print('Mapping written.')
