"""Check existing author citations and edit structure; does not adjudicate semantics."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
ART=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
mp=ART/'materials.json'; ap=ART/'author-review.json'; sp=ART/'material-seal.json'
materials=read(mp)['rows']; authors=read(ap)['items']; seal=read(sp)
assert sha(mp)==seal['materials_sha256'] and sha(ap)==seal['review_sha256']
m={x['id']:x for x in materials}; a={x['id']:x for x in authors}
assert len(m)==len(a)==36 and set(m)==set(a)
quote_count=0
for k in m:
    x,y=m[k],a[k]
    assert len(x['docs'])==5 and x['document_level']==y['state']
    assert y['proposed_probe_class']=={'S':'answer','I':'refuse','C':'conflict'}[y['state']]
    assert y['all_five_slots_checked'] is True
    for q in y['evidence']:
        assert 1<=q['slot']<=5 and q['quote'] in x['docs'][q['slot']-1]
        quote_count+=1
changed=Counter()
for base in sorted({x['original_id'] for x in materials}):
    for word in 'AB':
        s=m[f'{base}_S_{word}']; i=m[f'{base}_I_{word}']; c=m[f'{base}_C_{word}']
        assert s['question']==i['question']==c['question']
        for typ,x in [('S-I',i),('S-C',c)]:
            slots=tuple(j+1 for j,(u,v) in enumerate(zip(s['docs'],x['docs'])) if u!=v)
            assert slots==((1,) if typ=='S-I' else (2,))
            changed[typ+':'+','.join(map(str,slots))]+=1
    for state in 'SIC':
        x=m[f'{base}_{state}_A']; y=m[f'{base}_{state}_B']
        assert x['question']==y['question']
        slots=tuple(j+1 for j,(u,v) in enumerate(zip(x['docs'],y['docs'])) if u!=v)
        assert slots==((1,2) if state=='C' else (1,))
        changed['A-B-'+state+':'+','.join(map(str,slots))]+=1
print(json.dumps({'status':'passed','inputs':len(m),'author_records':len(a),'citations_matched':quote_count,
 'comparisons':dict(changed),'author_materials_sha256':sha(ap),'inputs_sha256':sha(mp),'seal_sha256':sha(sp),
 'limit':'quotation and edit identity do not prove entailment, absence of inference, semantic equivalence, gold labels or independence'},indent=2))
