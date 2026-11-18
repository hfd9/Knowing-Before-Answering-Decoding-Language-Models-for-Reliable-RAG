#!/usr/bin/env python3
"""CPU mock collection for the two exposed development cases; never loads references."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import query_determinacy_shared_extract_prototype as prototype

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1/public.json'


def mock(kind, request, case, mode):
    text, question = case['background'], request['question']
    if case['domain'] == 'integer':
        pairs = re.findall(r'(来源[甲乙]写：这次校准的读数是(\d+)单位。)', text)
        rules = {}
    else:
        pairs = re.findall(r'(来源[甲乙]写：本次检测代码是([A-Z0-9]+)。)', text)
        rules = dict(re.findall(r'([A-Z0-9]+)((?:不?适合)[^；。]+)', text))
    if len(pairs) != 2:
        raise ValueError('mock source syntax mismatch')
    values = [value for _, value in pairs]
    if kind == 'extract':
        if mode == 'extract_failure' and case['id'] == 'D7M4':
            return {'status': 'complete', 'output': '[true,2]'}
        return {'status': 'complete', 'output': json.dumps(values, ensure_ascii=False)}

    def answer(value):
        source = next(quote for quote, candidate in pairs if candidate == value)
        cites = [source]
        if case['domain'] == 'integer':
            match = re.search(r'(超过|低于)(\d+)单位', question)
            if not match:
                raise ValueError('mock question syntax mismatch')
            yes = int(value) > int(match[2]) if match[1] == '超过' else int(value) < int(match[2])
        else:
            rule = value + rules[value]
            cites.append(rule)
            target = re.search(r'是否适合(.+?)？', question)[1]
            yes = '不适合' + target not in rules[value] and '适合' + target in rules[value]
        out = 'Y' if yes else 'N'
        if mode == 'adversarial' and case['id'] == 'D7M4' and question == '该次校准读数是否超过45单位？':
            out = 'N' if out == 'Y' else 'Y'
        if mode == 'adversarial' and case['id'] == 'N3K6' and question == '按规则表，该零件是否适合室内储存？' and value == values[0]:
            cites = [pairs[1][0]]
        return {'value': value, 'answer': out, 'citations': cites}

    selected = list(request['values']) if request['values'] else values
    worlds = [answer(v) for v in selected]
    if kind == 'branch':
        payload = worlds[0]
    else:
        codes = [x['answer'] for x in worlds]
        payload = {'final': codes[0] if codes[0] == codes[1] else 'U', 'worlds': worlds}
    return {'status': 'complete', 'output': json.dumps(payload, ensure_ascii=False)}


def simulate(mode):
    raw = PUBLIC.read_bytes()
    public = json.loads(raw)
    if public['schema'] != 'two_world_development_public_v1' or len(public['cases']) != 2:
        raise ValueError('invalid pilot inputs')
    cases = {}
    for case in public['cases']:
        bg = {'id': case['id'], 'evidence': case['background'], 'domain': case['domain']}
        result = prototype.simulate(bg, case['questions'], lambda req: mock(req['kind'], req, case, mode))
        cases[case['id']] = result
    return {'schema': 'two_world_cpu_mock_results_v1', 'public_sha256': hashlib.sha256(raw).hexdigest(),
            'mode': mode, 'cases': cases,
            'model_calls': 0, 'simulated_calls': sum(len(x['calls']) for x in cases.values())}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('mode', choices=('normal', 'extract_failure', 'adversarial'))
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    payload = (json.dumps(simulate(args.mode), ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
    with args.output.open('xb') as stream:
        stream.write(payload)
    print(json.dumps({'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}))


if __name__ == '__main__':
    main()
