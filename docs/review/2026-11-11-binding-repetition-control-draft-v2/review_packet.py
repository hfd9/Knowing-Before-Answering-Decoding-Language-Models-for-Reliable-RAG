"""Create or verify an unscored review packet; separation is not blindness proof."""
import hashlib
import json
import secrets
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
PRIVATE=ROOT/'runs/binding-repetition-control-review-packet-20261111-v2'
MATERIAL=HERE/'materials.json'; PUBLIC=HERE/'review-packet.json'; COORD=PRIVATE/'coordinator.json'; META=HERE/'review-packet-audit.json'
def encoded(x): return (json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def verify():
    data=read(MATERIAL); public=read(PUBLIC); coord=read(COORD); meta=read(META)
    assert len(data['rows'])==len(public['items'])==len(coord['mapping'])==36
    assert meta['materials_sha256']==sha(MATERIAL.read_bytes())
    assert meta['public_sha256']==sha(PUBLIC.read_bytes()) and meta['coordinator_sha256']==sha(COORD.read_bytes())
    by={x['id']:x for x in data['rows']}; ids=set()
    for x in public['items']:
        assert set(x)=={'review_id','question','docs'} and len(x['docs'])==5
        assert x['review_id'] not in ids; ids.add(x['review_id'])
        src=by[coord['mapping'][x['review_id']]]
        assert x['question']==src['question'] and x['docs']==src['docs']
    assert ids==set(coord['mapping']) and len(set(coord['mapping'].values()))==36
    print(json.dumps({'status':'packet_integrity_passed','items':36,'scored':0,'reviewers':0,
        'full_blinding_certified':False,'coordinator_local_only':True}))
def main():
    if sys.argv[1:]==['--verify']: verify(); return
    if sys.argv[1:]: raise ValueError('use --verify or no arguments')
    if any(p.exists() for p in (PUBLIC,COORD,META)): raise ValueError('existing packet: preserve; use --verify')
    rows=read(MATERIAL)['rows']; assert len(rows)==36
    order=list(rows); secrets.SystemRandom().shuffle(order)
    mapping={}; items=[]
    for row in order:
        k='R'+secrets.token_hex(8)
        assert k not in mapping
        mapping[k]=row['id']; items.append({'review_id':k,'question':row['question'],'docs':row['docs']})
    packet={'purpose':'unscored review packet for already exposed development materials; not independent certification',
            'instruction':'For each question and all five documents, identify the target and evidence; decide whether it is supported, insufficient, conflicting, or unknown; cite exact passages with slot numbers and explain inferences. Record ambiguity. Do not infer or report any probe prediction.',
            'items':items}
    pb=encoded(packet); cb=encoded({'materials_sha256':sha(MATERIAL.read_bytes()),'public_sha256':sha(pb),'mapping':mapping})
    mb=encoded({'materials_sha256':sha(MATERIAL.read_bytes()),'public_sha256':sha(pb),'coordinator_sha256':sha(cb),
                'independent_reviewer_completed':False,'review_responses':0,'formal_labels':None,
                'limits':'text may be matched to public project files and conditions may be inferred; privacy of external context not certified'})
    PRIVATE.mkdir(parents=True,exist_ok=False)
    for p,b in [(COORD,cb),(PUBLIC,pb),(META,mb)]:
        with p.open('xb') as f: f.write(b)
    verify()
if __name__=='__main__': main()
