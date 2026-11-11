"""Connect sealed reviewer judgments to author references only after verifying seal."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;SEALED=HERE/'sealed'
ART=ROOT/'docs/review/2026-11-11-binding-repetition-control-draft-v2'
COORD=HERE/'coordinator/initial-coordinator.json'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
seal=read(SEALED/'seal.json');assert seal['status']=='sealed_before_author_mapping'
for name,expected in seal['files_sha256'].items():assert sha(SEALED/name)==expected,name
meta=read(ART/'review-packet-audit.json');assert sha(COORD)==meta['coordinator_sha256']
coord=read(COORD);author=read(ART/'author-review.json')['items'];refs={x['id']:x for x in author}
mapping=coord['mapping'];assert len(mapping)==len(refs)==36
records=[]; states={'answerable':'answer','insufficient':'refuse','conflicting':'conflict','unknown':'unknown'}
for k in range(1,7):
    events=[json.loads(x) for x in (SEALED/f'response-{k}.jsonl').read_text().splitlines() if x.strip()]
    msg=next(x['item']['text'] for x in events if x['type']=='item.completed' and x['item']['type']=='agent_message').strip()
    if msg.startswith('```'):msg=msg.split('\n',1)[1].rsplit('```',1)[0].strip()
    for x in json.loads(msg)['items']:
        src=mapping[x['review_id']];a=refs[src];state=states[x['state']]
        value_equal=(set(x['value_or_values'])==set(a['assigned_target_values'])) if state in ('answer','conflict') else None
        author_class={'S':'answer','I':'refuse','C':'conflict'}[a['state']]
        records.append({'review_id':x['review_id'],'source_id':src,'base':src.split('_')[1],
                        'author_state':a['state'],'author_class':author_class,'review_state':x['state'],
                        'class_match_author':None if state=='unknown' else state==author_class,
                        'answer_values_match_author':value_equal,'review_values':x['value_or_values'],
                        'review_reason':x['reason'],'review_evidence':x['evidence']})
assert len(records)==36 and len({x['source_id'] for x in records})==36
counts={'matched':sum(x['class_match_author'] is True for x in records),'disagreement':sum(x['class_match_author'] is False for x in records),
        'unknown':sum(x['class_match_author'] is None for x in records),
        'answer_or_conflict_values_match':sum(x['answer_values_match_author'] is True for x in records),
        'answer_or_conflict_values_differ':sum(x['answer_values_match_author'] is False for x in records)}
out={'status':'connected_after_seal','counts':counts,'reviewers':1,'formal_independent_approvals':0,
     'limitations':'same reviewer six batches; private context and error independence not certified; citations do not prove semantics',
     'seal_sha256':sha(SEALED/'seal.json'),'coordinator_sha256':sha(COORD),'author_reference_sha256':sha(ART/'author-review.json'),
     'records':records}
p=HERE/'connected.json';data=(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
if p.exists():assert p.read_bytes()==data
else:p.write_bytes(data)
print(json.dumps(counts,ensure_ascii=False))
