from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys
c=Path('/tmp/scope-review-20261107-01/coordinator')
sys.path.insert(0,'/large_disk/wf/研究代码/Knowing-Before-Answering-Decoding-Language-Models-for-Reliable-RAG/scripts')
import verify_explanation_scope_input_review_batch as verify
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
packet=c/'input_packet.json'; audit=c/'audit2-response.txt'; completion=c/'completion-response.txt'
finish=json.loads(completion.read_text())
if not isinstance(finish.get('review_completed'), str) or not finish['review_completed'].startswith('All 48 items received batch assessments.'): raise ValueError('reviewer did not declare 48 batch assessments')
rows=[]; batches=[]; statements=[]
for b in range(1,7):
 start=(b-1)*8+1; end=b*8; response=c/f'batch{b:02d}-response.txt'; events=c/f'batch{b:02d}-events.jsonl'; task=c/f'batch{b:02d}-task.txt'
 check=verify.verify(packet,response,events,start,end)
 data=json.loads(response.read_text()); lines=[json.loads(x) for x in events.read_text().splitlines()]; threads=[x.get('thread_id') for x in lines if x.get('type')=='thread.started']
 if threads!=['01a1b4e9-eb7a-7a31-bf38-4360cac26cd3']: raise ValueError('unexpected reviewer session')
 rows.extend(data['items']); batches.append({'batch':data['batch'],'response_sha256':h(response),'events_sha256':h(events),'task_sha256':h(task),'visible_items':check['visible_complete_items'],'exact_quote_occurrences':check['exact_quote_occurrences']})
 statements.append({'batch':data['batch'],'exposure_statement':data['exposure_statement'],'reading_statement':data['reading_statement'],'limitations':data['limitations']})
if len(rows)!=48 or len({x['item_id'] for x in rows})!=48: raise ValueError('incomplete review')
review={'status':'reviewer_completed_input_only_not_formal_independent_approval','reviewer_id':'SCOPECLI20261107R01','thread_id':'01a1b4e9-eb7a-7a31-bf38-4360cac26cd3','input_packet_sha256':h(packet),'audit_sha256':h(audit),'completion_declaration_sha256':h(completion),'batches':batches,'batch_statements':statements,'items':rows}
reviewpath=c/'input_review_sealed.json'
with reviewpath.open('x') as f:
 json.dump(review,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
seal={'sealed_at':datetime.now(timezone.utc).isoformat(),'input_review_sha256':h(reviewpath),'input_packet_sha256':h(packet),'audit_sha256':h(audit),'completion_declaration_sha256':h(completion),'reviewed_items':48,'batches':6,'condition_mapping_or_author_judgments_delivered_before_seal':False,'semantic_independent_approval':False,'reviewer_completion_declaration':finish['review_completed'],'packet_hash_was_supplied_to_reviewer':True,'reviewer_produced_offset_files':False,'note':'Hash and timing bind preserved responses; they do not certify private context, comprehension, truth, or power-loss durability.'}
with (c/'input_seal.json').open('x') as f:
 json.dump(seal,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps(seal,ensure_ascii=False,indent=2))
