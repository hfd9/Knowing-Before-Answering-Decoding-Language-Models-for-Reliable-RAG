"""Describe post-hoc lexical overlap in existing 36 inputs; no model or training."""
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
MATERIALS=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1/materials.json'
SEAL=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1/material-seal.json'
STATES=ROOT/'docs/review/2026-11-11-new-controlled-exploration-results-v1/source/states.json'
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(MATERIALS)==read(SEAL)['materials_sha256']
inputs=read(MATERIALS)['rows']; states=read(STATES)['records'][1:]
assert len(inputs)==len(states)==36
records={x['id']:x for x in states}
assert set(records)=={x['id'] for x in inputs}
rows=[]
for x in inputs:
    assert len(x['docs'])==5
    a,b=(set(re.findall(r'[a-z0-9]+',t.lower())) for t in x['docs'][:2])
    assert a|b
    z=records[x['id']]
    rows.append({'id':x['id'],'base':x['original_id'],'state':x['document_level'],'expression':x['question_level'],
                 'slot1_unique_words':len(a),'slot2_unique_words':len(b),
                 'intersection':len(a&b),'union':len(a|b),'jaccard':len(a&b)/len(a|b),
                 'pred':z['probe_pred'],'conflict_probability':z['probe_probabilities']['conflict']})
with (OUT/'overlap.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
groups={}
for s in 'SIC':
    x=[r['jaccard'] for r in rows if r['state']==s]
    assert len(x)==12
    groups[s]={'n':len(x),'min':min(x),'mean':statistics.mean(x),'max':max(x)}
by={(r['base'],r['expression'],r['state']):r for r in rows}
assert len(by)==36
comparisons={}
for s in 'SI':
    delta=[by[b,e,'C']['jaccard']-by[b,e,s]['jaccard'] for b in sorted({r['base'] for r in rows}) for e in 'AB']
    comparisons['C_minus_'+s]={'n':len(delta),'positive':sum(x>0 for x in delta),'min':min(delta),'max':max(delta)}
print(json.dumps({'status':'passed','method':'lowercase ASCII alphanumeric unigram set Jaccard between slots 1 and 2',
 'timing':'post-hoc, slots selected after observing construction', 'groups':groups,'paired_differences':comparisons,
 'no_fit_or_threshold':True,'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (MATERIALS,SEAL,STATES)},
 'rows_sha256':sha(OUT/'overlap.csv'),
 'limits':'6 related bases, author-constructed states; not held-out classifier accuracy, no causal inference'},indent=2))
