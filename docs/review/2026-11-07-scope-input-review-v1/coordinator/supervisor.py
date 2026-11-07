from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, sys
c=Path('/tmp/scope-review-20261107-01/coordinator')
n=Path('/tmp/scope-review-20261107-01/neutral')
verifier=Path('/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG/scripts/verify_explanation_scope_input_review_batch.py')
packet=c/'input_packet.json'
thread='01a1b4e9-eb7a-7a31-bf38-4360cac26cd3'
for batch in range(2,7):
 start=(batch-1)*8+1; end=batch*8; stem=f'batch{batch:02d}'
 response=c/f'{stem}-response.txt'; events=c/f'{stem}-events.jsonl'; err=c/f'{stem}-stderr.txt'; task=c/f'{stem}-task.txt'
 if any(x.exists() for x in (response,events,err)):
  print(stem, 'output already exists; stopping to preserve it',flush=True); sys.exit(2)
 print(stem, 'started',datetime.now(timezone.utc).isoformat(),flush=True)
 with task.open('rb') as fin, events.open('xb') as fout, err.open('xb') as ferr:
  code=subprocess.run(['codex','exec','resume','--skip-git-repo-check','--json','-o',str(response),thread,'-'],cwd=n,stdin=fin,stdout=fout,stderr=ferr).returncode
 if code:
  print(stem,'CLI failed',code,'stopping',flush=True); sys.exit(code)
 result=subprocess.run([sys.executable,'-B',str(verifier),'--packet',str(packet),'--response',str(response),'--events',str(events),'--start',str(start),'--end',str(end)],capture_output=True,text=True)
 if result.returncode:
  (c/f'{stem}-validation-failure.txt').write_text(result.stderr)
  print(stem,'validation failed; preserved raw output and stopping',flush=True); sys.exit(3)
 validation=json.loads(result.stdout)
 (c/f'{stem}-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
 checkpoint={'completed_at':datetime.now(timezone.utc).isoformat(),'batch':stem,'response_sha256':hashlib.sha256(response.read_bytes()).hexdigest(),'events_sha256':hashlib.sha256(events.read_bytes()).hexdigest(),'validation_sha256':hashlib.sha256((c/f'{stem}-validation.json').read_bytes()).hexdigest(),'semantic_independence_approved':False}
 (c/f'{stem}-checkpoint.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+'\n')
 print(stem,'complete:',validation['reviewed_items'],'items,',validation['exact_quote_occurrences'],'exact quote occurrences',flush=True)
print('All five remaining batches produced and structurally validated; no semantic or independence approval',flush=True)
