"""Construct the user-requested, informed six-base probe development materials on CPU."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'prompts/new_controlled_probe_20261111_v1.json'
OUT = ROOT / 'docs/review/2026-11-11-new-controlled-exploration-v1'
STATES = ('S', 'I', 'C')
WORDS = ('A', 'B')
MAP = {'S': 'answer', 'I': 'refuse', 'C': 'conflict'}

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def construct(spec):
    assert len(spec['scenarios']) == 6
    rows, reviews = [], []
    for s in spec['scenarios']:
        assert len(s['background']) == 3
        assert all(len(s[k]) == 2 for k in ('support', 'missing', 'conflict'))
        for state in STATES:
            for idx, wording in enumerate(WORDS):
                first = s['missing'][idx] if state == 'I' else s['support'][idx]
                second = s['conflict'][idx] if state == 'C' else s['neutral']
                docs = [first, second] + list(s['background'])
                row = dict(id=f"{s['id']}_{state}_{wording}", original_id=s['id'],
                           question_level=wording, document_level=state,
                           question=s['question'], docs=docs, source=None)
                evidence = {'S': [{'slot':1, 'quote':first}],
                            'I': [{'slot':1, 'quote':first}, {'slot':2, 'quote':second}],
                            'C': [{'slot':1, 'quote':first}, {'slot':2, 'quote':second},
                                  {'slot':3, 'quote':s['background'][0]}]}[state]
                review = dict(id=row['id'], target={'entity':s['entity'], 'field':s['field'], 'condition':s['condition']},
                              state=state, proposed_probe_class=MAP[state],
                              values=([s['value']] if state == 'S' else [] if state == 'I' else [s['value'], s['alternate']]),
                              evidence=evidence, all_five_slots_checked=True,
                              rationale=s['review'], expression_pair='informed_author_assessment_preserves_target_relation',
                              status='informed_author_reference_not_independent_gold')
                rows.append(row); reviews.append(review)
    assert len(rows) == len(reviews) == 36
    return rows, reviews

def main():
    assert len(sys.argv) == 2 and sys.argv[1] in ('write', 'verify')
    spec_bytes = SPEC.read_bytes(); spec = json.loads(spec_bytes)
    rows, reviews = construct(spec)
    materials = {'schema_version':1, 'scope':spec['disclosure'], 'rows':rows}
    review = {'schema_version':1, 'reviewer':'same informed author/assistant',
              'disclosure':'Author-written assessment after exposure to prior experiments; no independent semantic validation.',
              'review_before_new_probe_output':True, 'items':reviews}
    mb, rb = encoded(materials), encoded(review)
    seal = encoded({'spec_sha256':sha(spec_bytes), 'materials_sha256':sha(mb), 'review_sha256':sha(rb),
                    'new_probe_predictions_observed':False, 'formal_labels':None,
                    'informed_reference_only':True})
    outputs = {'materials.json':mb,'author-review.json':rb,'material-seal.json':seal}
    OUT.mkdir(parents=True,exist_ok=True)
    for name, data in outputs.items():
        p=OUT/name
        if sys.argv[1]=='write':
            if p.exists():
                if p.read_bytes()!=data: raise RuntimeError('refuse to overwrite '+str(p))
            else: p.write_bytes(data)
        elif p.read_bytes()!=data: raise RuntimeError('material mismatch '+str(p))
    print(json.dumps({'status':'authored_informed_reference_only','bases':6,'inputs':36,'slots':180,
                      'materials_sha256':sha(mb),'review_sha256':sha(rb)}))
if __name__ == '__main__': main()
