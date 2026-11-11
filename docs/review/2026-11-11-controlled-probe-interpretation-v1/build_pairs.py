"""Reconstruct 42 descriptive comparisons from archived inputs and prefill records."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/review/2026-11-11-new-controlled-exploration-results-v1/source'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
inputs = read(SOURCE / 'materials/inputs.json')[1:]
records = read(SOURCE / 'states.json')['records'][1:]
author_path = ROOT / 'docs/review/2026-11-11-new-controlled-exploration-v1/author-review.json'
authors = read(author_path)['items']
rows = {r['id']:r for r in inputs}
results = {r['id']:r for r in records}
references = {r['id']:r for r in authors}
assert len(rows) == len(results) == len(references) == 36
old = read(SOURCE / 'report.json')['pairs']
out = []
for p in old:
    l, r = p['left']['id'], p['right']['id']
    a, b = rows[l], rows[r]
    x, y = results[l], results[r]
    assert a['question'] == b['question']
    changes = [i for i,(u,v) in enumerate(zip(a['docs'],b['docs']),1) if u != v]
    assert changes == ([1] if p['type']=='S-I' else [2] if p['type']=='S-C' else [1,2] if a['document_level']=='C' else [1])
    assert x['probe_pred'] == p['left']['pred'] and y['probe_pred'] == p['right']['pred']
    for z, side in [(x,'left'),(y,'right')]:
        assert z['probe_probabilities'] == p[side]['probs']
        assert references[z['id']]['proposed_probe_class'] == p[side]['author_ref']
    d = {'base':p['base'],'comparison':p['type'],'state':p.get('state',''),'wording':p.get('wording',''),
         'left_id':l,'right_id':r,'changed_slots':','.join(map(str,changes)),
         'left_changed_text':' | '.join(a['docs'][i-1] for i in changes),
         'right_changed_text':' | '.join(b['docs'][i-1] for i in changes),
         'left_tokens':x['input_tokens'],'right_tokens':y['input_tokens'],
         'token_delta':y['input_tokens']-x['input_tokens'],
         'left_reference':references[l]['proposed_probe_class'],'right_reference':references[r]['proposed_probe_class'],
         'left_class':x['probe_pred'],'right_class':y['probe_pred'],
         'left_matches_author':x['probe_pred']==references[l]['proposed_probe_class'],
         'right_matches_author':y['probe_pred']==references[r]['proposed_probe_class']}
    for cls in ['answer','refuse','conflict']:
        d['left_'+cls] = x['probe_probabilities'][cls]
        d['right_'+cls] = y['probe_probabilities'][cls]
        d['delta_'+cls] = y['probe_probabilities'][cls]-x['probe_probabilities'][cls]
    out.append(d)
assert len(out)==42 and Counter(x['comparison'] for x in out)=={'A-B':18,'S-I':12,'S-C':12}
with (OUT/'pairs.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=out[0].keys(),lineterminator='\n'); w.writeheader(); w.writerows(out)
manifest={str(p.relative_to(ROOT)):sha(p) for p in [SOURCE/'materials/inputs.json',SOURCE/'states.json',SOURCE/'report.json',author_path]}
(OUT/'source-hashes.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pairs':len(out),'types':dict(Counter(x['comparison'] for x in out)),
 'changed_slots':dict(Counter(x['comparison']+':'+x['changed_slots'] for x in out)),
 'pairs_sha256':sha(OUT/'pairs.csv'),'source_hashes':manifest},indent=2))
