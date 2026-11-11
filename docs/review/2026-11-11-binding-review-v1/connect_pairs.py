"""Connect pair follow-up after its own seal and validate delivered payload binding."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent; SEALED=HERE/'paired-sealed'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
seal=read(SEALED/'seal.json');assert seal['status']=='pair_followup_sealed_before_pair_mapping'
for name,expected in seal['files_sha256'].items():assert sha(SEALED/name)==expected
assert sha(HERE/'sealed/seal.json')==seal['initial_seal_sha256']
mp=read(HERE/'coordinator/pair-map.json');coord=read(HERE/'coordinator/initial-coordinator.json')['mapping']
public={x['review_id']:x for x in read(HERE/'sealed/review-packet.json')['items']};records=[]
assert len(mp)==18
for i in range(1,4):
    sent=json.loads((SEALED/f'pair-batch-{i}.txt').read_text().split('\n',1)[1])['items'];by={x['pair_id']:x for x in sent}
    ev=[json.loads(x) for x in (SEALED/f'pair-response-{i}.jsonl').read_text().splitlines() if x.strip()]
    msg=next(x['item']['text'] for x in ev if x['type']=='item.completed' and x['item']['type']=='agent_message').strip()
    if msg.startswith('```'):msg=msg.split('\n',1)[1].rsplit('```',1)[0].strip()
    for x in json.loads(msg)['items']:
        q=by[x['pair_id']];m=mp[x['pair_id']];base=m['base'];state=m['state']
        for side in ('left','right'):
            rid=m[side+'_review_id'];src=public[rid]
            assert q[side]=={'question':src['question'],'docs':src['docs']}
            assert coord[rid]==f'bind_{base}_{state}_'+('A' if side=='left' else 'B')
        records.append({'pair_id':x['pair_id'],'base':base,'author_state':state,'relation':x['relation'],
                        'reason':x['reason'],'left_evidence':x['left_evidence'],'right_evidence':x['right_evidence']})
assert len(records)==len(mp)==18 and len({(x['base'],x['author_state']) for x in records})==18
counts={k:sum(x['relation']==k for x in records) for k in ('same','different','unknown')}
out={'status':'connected_after_pair_seal','counts':counts,'reviewers':1,'additional_reviewers':0,
     'seal_sha256':sha(SEALED/'seal.json'),'pair_map_sha256':sha(HERE/'coordinator/pair-map.json'),'records':records}
data=(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();p=HERE/'paired-connected.json'
if p.exists():assert p.read_bytes()==data
else:p.write_bytes(data)
print(json.dumps(counts))
