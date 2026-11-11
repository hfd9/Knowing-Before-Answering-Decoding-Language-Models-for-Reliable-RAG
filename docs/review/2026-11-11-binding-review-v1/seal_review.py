"""Seal reviewed payloads and raw session events before connecting author mappings."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
WORK=Path('/tmp/binding-review-20261111');SEALED=HERE/'sealed'; PACKET=ROOT/'docs/review/2026-11-11-binding-repetition-control-draft-v2/review-packet.json'
def sha(data):return hashlib.sha256(data).hexdigest()
assert not (SEALED/'seal.json').exists(),'already sealed; preserve'
manifest=json.loads((WORK/'batch-manifest.json').read_text()); assert len(manifest)==6
exposure=[json.loads(x) for x in (WORK/'exposure.jsonl').read_text().splitlines() if x]
thread=exposure[0]['thread_id'];assert exposure[0]['type']=='thread.started' and exposure[-1]['type']=='turn.completed'
inputs=[('review-packet.json',PACKET),('exposure.jsonl',WORK/'exposure.jsonl'),('batch-manifest.json',WORK/'batch-manifest.json')]
checks=[]
for i in range(1,7):
    prompt=WORK/f'batch-{i}.txt';response=WORK/f'response-{i}.jsonl'
    assert sha(prompt.read_bytes())==manifest[i-1]['sha256']
    events=[json.loads(x) for x in response.read_text().splitlines() if x]
    assert events[0]['thread_id']==thread and events[-1]['type']=='turn.completed'
    result=subprocess.run(['/large_disk/wf/miniconda3/envs/kba-rag/bin/python','-B',str(HERE/'check_batch.py'),str(i)],check=True,text=True,capture_output=True)
    checks.append(json.loads(result.stdout));inputs.extend([(prompt.name,prompt),(response.name,response)])
assert sum(x['items'] for x in checks)==36 and sum(x['quotes'] for x in checks)==180
files={}
for name,src in inputs:
    data=src.read_bytes();dst=SEALED/name
    with dst.open('xb') as f:f.write(data)
    files[name]=sha(data)
seal={'status':'sealed_before_author_mapping','sealed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'thread_id':thread,'reviewers':1,'batches':6,'reviewed_inputs':36,'verified_quote_occurrences':180,
      'observable_tool_calls':0,'independent_private_context_certified':False,'formal_approval':0,
      'files_sha256':files,'public_packet_checks':checks}
with (SEALED/'seal.json').open('x',encoding='utf-8') as f:json.dump(seal,f,indent=2,ensure_ascii=False);f.write('\n')
print(json.dumps({'status':seal['status'],'reviewers':1,'inputs':36,'quotes':180,'files':len(files),'sealed_at_utc':seal['sealed_at_utc']}))
