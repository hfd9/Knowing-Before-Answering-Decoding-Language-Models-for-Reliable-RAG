#!/usr/bin/env python3
"""Build a traceable per-question table for the exposed 12-case development set."""
import hashlib
import json
from pathlib import Path
import query_determinacy_development12_verify as verifier

BASE = Path(__file__).resolve().parents[1] / 'docs/review/2026-11-18-two-case-cpu-v1'


def audit():
    checked = verifier.verify()
    rawp, rawr, rawo = ((BASE/name).read_bytes() for name in ('public-12-v2.json', 'reference-12-v2.json', 'overlap-12-v2.json'))
    public, ref, overlap = map(json.loads, (rawp, rawr, rawo))
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if overlap['public_sha256'] != sha(rawp):
        raise ValueError('overlap source mismatch')
    screened = {x['case']: x for x in overlap['cases']}
    rows = []
    for case in public['cases']:
        r = ref['cases'][case['id']]
        s = screened[case['id']]
        for q in case['questions']:
            answer = r['questions'][q['id']]
            checks = s['questions'][q['id']]['counts']
            rows.append({'case': case['id'], 'question': q['id'], 'question_text': q['text'],
                         'domain': case['domain'], 'worlds': r['worlds'],
                         'world_answers': answer['world_answers'], 'final': answer['final'],
                         'author_rationale': answer['rationale'], 'prior_question_counts': checks,
                         'prior_background_counts': s['background']['counts'],
                         'overlap_short_approximation': 'unknown' if checks.get('short', 0) else 'applicable',
                         'independent_semantic_review': False})
    return {'schema': 'shared_material_review_v1', 'public_sha256': sha(rawp), 'reference_sha256': sha(rawr),
            'overlap_sha256': sha(rawo), 'restricted_verification': checked, 'rows': rows,
            'limits': 'Same informed author; explicit exhaustiveness is a premise; substring citation is not semantic proof; short comparisons, 380, other history and pretraining remain unknown.'}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))
