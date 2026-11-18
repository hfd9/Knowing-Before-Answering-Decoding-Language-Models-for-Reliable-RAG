#!/usr/bin/env python3
"""Independent structural and restricted semantic check of author materials."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'docs/review/2026-11-18-two-case-cpu-v1'


def verify():
    public_raw = (BASE / 'public-12-v2.json').read_bytes()
    ref_raw = (BASE / 'reference-12-v2.json').read_bytes()
    public, ref = json.loads(public_raw), json.loads(ref_raw)
    cases = public['cases']
    if len(cases) != 12 or len({c['id'] for c in cases}) != 12 or set(ref['cases']) != {c['id'] for c in cases}:
        raise ValueError('case identity mismatch')
    counts, families = Counter(), Counter()
    for case in cases:
        background = case['background']
        if '恰为' not in background or '两种情况均' not in background or '来源甲' not in background or '来源乙' not in background:
            raise ValueError('missing explicit two-world language')
        r = ref['cases'][case['id']]
        worlds = r['worlds']
        if len(worlds) != 2 or len({w['value'] for w in worlds}) != 2 or len(case['questions']) != 3:
            raise ValueError('world/question count mismatch')
        if set(r['questions']) != {q['id'] for q in case['questions']}:
            raise ValueError('question identity mismatch')
        for world in worlds:
            for key in ('source_quote', 'rule_quote'):
                if key in world and world[key] not in background:
                    raise ValueError('reference quote absent')
        if worlds[0]['value'] not in worlds[0]['source_quote'] or worlds[1]['value'] not in worlds[1]['source_quote']:
            raise ValueError('source/value mismatch')
        family = case['domain']
        families[family] += 1
        classes = []
        for question in case['questions']:
            q = question['text']
            if family == 'integer':
                m = re.search(r'(超过|低于)(\d+)', q)
                if not m:
                    raise ValueError('unsupported numeric question')
                actual = [('Y' if (int(w['value']) > int(m[2]) if m[1] == '超过' else int(w['value']) < int(m[2])) else 'N') for w in worlds]
            elif family == 'identifier':
                m = re.search(r'是否适合(.+?)？', q)
                if not m:
                    raise ValueError('unsupported category question')
                actual = []
                for w in worlds:
                    rule = w['rule_quote']
                    if '不适合' + m[1] in rule:
                        actual.append('N')
                    elif '适合' + m[1] in rule:
                        actual.append('Y')
                    else:
                        raise ValueError('missing explicit property rule')
            else:
                raise ValueError('unsupported family')
            expected = r['questions'][question['id']]
            final = actual[0] if actual[0] == actual[1] else 'U'
            if expected['world_answers'] != actual or expected['final'] != final:
                raise ValueError('reference does not match semantics')
            classes.append(final)
            counts[final] += 1
        if sorted(classes) != ['N', 'U', 'Y']:
            raise ValueError('each case requires Y/N/U')
    return {'cases': len(cases), 'questions': sum(counts.values()), 'families': dict(families), 'finals': dict(counts),
            'public_sha256': hashlib.sha256(public_raw).hexdigest(), 'reference_sha256': hashlib.sha256(ref_raw).hexdigest(),
            'note': 'restricted parser and author materials; not independent semantic review'}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
