"""Read-only replay of raw sealed reviews, citations, mappings and count summaries."""
import collections
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
S=HERE/'sealed';P=HERE/'paired-sealed';ART=ROOT/'docs/review/2026-11-11-binding-repetition-control-draft-v2'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def payload(path):
    ev=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    assert ev[0]['type']=='thread.started' and ev[-1]['type']=='turn.completed'
    msg=[x['item'] for x in ev if x['type']=='item.completed'];assert len(msg)==1 and msg[0]['type']=='agent_message'
    t=msg[0]['text'].strip()
    if t.startswith('```'):t=t.split('\n',1)[1].rsplit('```',1)[0].strip()
    return json.loads(t)['items'],ev[-1].get('usage',{})
initial=read(S/'seal.json'); pair=read(P/'seal.json')
for home,seal in [(S,initial),(P,pair)]:
    for name,d in seal['files_sha256'].items():assert sha(home/name)==d
assert pair['initial_seal_sha256']==sha(S/'seal.json') and initial['thread_id']==pair['thread_id']
assert sha(S/'review-packet.json')==sha(ART/'review-packet.json')
coord=read(HERE/'coordinator/initial-coordinator.json'); meta=read(ART/'review-packet-audit.json')
assert sha(HERE/'coordinator/initial-coordinator.json')==meta['coordinator_sha256']
author={x['id']:x for x in read(ART/'author-review.json')['items']};mapping=coord['mapping']
rows=[];pairrows=[]; usage_events=[]; reconnect_events=[]
for i in range(1,7):
    subprocess.run(['/large_disk/wf/miniconda3/envs/kba-rag/bin/python','-B',str(HERE/'check_batch.py'),str(i),'--work',str(S)],check=True,capture_output=True)
    response=S/f'response-{i}.jsonl'
    x,u=payload(response);rows.extend(x);usage_events.append({'event':f'response-{i}',**u})
    reconnect_events.extend({'event':f'response-{i}','message':e['message']} for e in map(json.loads,response.read_text().splitlines()) if e['type']=='error')
for i in range(1,4):
    subprocess.run(['/large_disk/wf/miniconda3/envs/kba-rag/bin/python','-B',str(HERE/'check_pair_batch.py'),str(i),'--work',str(P)],check=True,capture_output=True)
    response=P/f'pair-response-{i}.jsonl'
    x,u=payload(response);pairrows.extend(x);usage_events.append({'event':f'pair-response-{i}',**u})
    reconnect_events.extend({'event':f'pair-response-{i}','message':e['message']} for e in map(json.loads,response.read_text().splitlines()) if e['type']=='error')
u=[json.loads(x) for x in (S/'exposure.jsonl').read_text().splitlines() if x][-1]['usage']
usage_events.insert(0,{'event':'exposure',**u})
assert len(rows)==36 and len({x['review_id'] for x in rows})==36 and set(mapping)=={x['review_id'] for x in rows}
matrix=collections.Counter((author[mapping[x['review_id']]]['state'],x['state']) for x in rows)
assert matrix=={('S','answerable'):12,('I','insufficient'):12,('C','conflicting'):12}
assigned=[x for x in rows if x['state'] in ('answerable','conflicting')]
assert len(assigned)==24 and all(set(x['value_or_values'])==set(author[mapping[x['review_id']]]['assigned_target_values']) for x in assigned)
insufficient=[x for x in rows if x['state']=='insufficient']
assert len(insufficient)==12 and all(set(x['value_or_values'])==set(author[mapping[x['review_id']]]['possible_values']) for x in insufficient)
assert len(pairrows)==18 and len({x['pair_id'] for x in pairrows})==18
assert collections.Counter(x['relation'] for x in pairrows)=={'same':18}
subprocess.run(['/large_disk/wf/miniconda3/envs/kba-rag/bin/python','-B',str(HERE/'connect_review.py')],check=True,capture_output=True)
subprocess.run(['/large_disk/wf/miniconda3/envs/kba-rag/bin/python','-B',str(HERE/'connect_pairs.py')],check=True,capture_output=True)
print(json.dumps({'status':'passed','inputs':36,'state_matches':36,'explicit_value_matches':24,
 'I_possible_values_match':12,'reviewer_pairs_same':18,'single_input_quote_occurrences':180,'pair_quote_occurrences':108,
 'reviewers':1,'formal_approvals':0,'reconnect_events':reconnect_events,'usage_events_reported':usage_events,
 'limits':'Usage may be cumulative; do not sum events or infer billing. Replay and literal citations do not certify semantic truth, hidden context, reviewer independence, or billing'},ensure_ascii=False,indent=2))
