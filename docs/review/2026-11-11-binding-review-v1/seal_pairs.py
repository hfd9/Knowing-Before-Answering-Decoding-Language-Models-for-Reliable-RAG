"""Seal same-reviewer pair follow-up before linking pair IDs to author states."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
WORK=Path('/tmp/binding-review-20261111');OUT=HERE/'paired-sealed'
def sha(b):return hashlib.sha256(b).hexdigest()
assert not (OUT/'seal.json').exists()
initial=json.loads((HERE/'sealed/seal.json').read_text());assert initial['status']=='sealed_before_author_mapping'
manifest=json.loads((WORK/'pair-manifest.json').read_text());assert len(manifest)==3
files={}; checks=[]
sources=[WORK/'pair-manifest.json']
for i in range(1,4):
    p=WORK/f'pair-batch-{i}.txt';r=WORK/f'pair-response-{i}.jsonl'
    assert sha(p.read_bytes())==manifest[i-1]['sha256']
    events=[json.loads(x) for x in r.read_text().splitlines() if x]
    assert events[0]['type']=='thread.started' and events[0]['thread_id']==initial['thread_id'] and events[-1]['type']=='turn.completed'
    z=subprocess.run(['/large_disk/wf/miniconda3/envs/kba-rag/bin/python','-B',str(HERE/'check_pair_batch.py'),str(i)],check=True,text=True,capture_output=True)
    checks.append(json.loads(z.stdout));sources.extend([p,r])
assert sum(x['pairs'] for x in checks)==18
for src in sources:
    b=src.read_bytes()
    with (OUT/src.name).open('xb') as f:f.write(b)
    files[src.name]=sha(b)
seal={'status':'pair_followup_sealed_before_pair_mapping','sealed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'initial_seal_sha256':sha((HERE/'sealed/seal.json').read_bytes()),'thread_id':initial['thread_id'],
      'reviewers':1,'additional_reviewers':0,'pairs':18,'files_sha256':files,'public_pair_checks':checks,
      'limits':'same session after individual judgments; grouping delivered; private context not certified'}
with (OUT/'seal.json').open('x',encoding='utf-8') as f:json.dump(seal,f,indent=2,ensure_ascii=False);f.write('\n')
print(json.dumps({'status':seal['status'],'pairs':18,'same':sum(x['relations']['same'] for x in checks),
                  'different':sum(x['relations']['different'] for x in checks),'unknown':sum(x['relations']['unknown'] for x in checks),
                  'citations':sum(x['citation_occurrences'] for x in checks)}))
