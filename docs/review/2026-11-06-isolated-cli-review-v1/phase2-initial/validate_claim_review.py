import json,hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read('input_packet.json')['items'];o=read('output_packet.json')['items']
template=read('claim_review_template.json'); r=read('claim_review.json');log=read('output_reading_log.json');context=read('output_context.json');seal=read('input_seal.json')
baseline=read('stage2_preservation_baseline.json')
expected=[f'Q{n:03d}' for n in range(1,56)]
for rows in [p,o,template['items'],r['items'],log['items']]:assert [x['item_id'] for x in rows]==expected
assert r['reviewer_id']==log['reviewer_id']==context['reviewer_id']=='CLI20261106R01'
assert r['sealed_input_review_sha256']==seal['input_review_sha256']==sha('input_review.json')
assert all(sha(path)==h for path,h in baseline.items())
assert datetime.fromisoformat(context['reviewed_at']).utcoffset() is not None
unit_count=atom_count=doc_citation_count=output_citation_count=0
judgments=Counter();roles=Counter()
for ip,op,blank,row,lr in zip(p,o,template['items'],r['items'],log['items']):
 assert set(blank)==set(row)
 assert row['status']=='reviewed' and row['full_answer_claim_coverage_confirmed'] is True
 assert type(row['gives_specific_target_answer']) is bool
 assert len(row['claim_reviews'])==len(blank['claim_reviews'])==len(op['candidate_sentence_units'])
 assert lr['answer_sha256_utf8']==hashlib.sha256(op['answer'].encode()).hexdigest()
 assert lr['answer_unicode_characters']==len(op['answer'])
 assert lr['answer_utf8_bytes']==len(op['answer'].encode())
 assert lr['displayed_character_ranges']==[[0,len(op['answer'])]]
 assert lr['original_unit_mappings']==op['candidate_sentence_units']
 assert lr['question_sha256_utf8']==hashlib.sha256(ip['question'].encode()).hexdigest()
 assert lr['document_slot_hashes_sha256_utf8']==[hashlib.sha256(d.encode()).hexdigest() for d in ip['documents']]
 assert lr['complete_answer_read_declared'] and lr['full_semantic_claim_coverage_declared']
 last=0; ids=set(); atoms=[]
 for source,bu,unit in zip(op['candidate_sentence_units'],blank['claim_reviews'],row['claim_reviews']):
  unit_count+=1
  assert set(unit)==set(bu)
  assert unit['unit_id']==bu['unit_id']==source['unit_id']
  assert unit['source_span']==bu['source_span']==source
  assert source['start']==last and source['end']>source['start'];last=source['end']
  assert op['answer'][source['start']:source['end']]==source['quote']
  assert source['text_sha256']==hashlib.sha256(op['answer'].encode()).hexdigest()
  for field in ['document_support','counterevidence','missing_link','ambiguity','judgment']:assert unit[field] is None
  assert isinstance(unit['atomic_claims'],list) and unit['atomic_claims']
  for a in unit['atomic_claims']:
   atom_count+=1;atoms.append(a);judgments[a['judgment']]+=1;roles[a['role']]+=1
   assert set(a)=={'claim_id','claim','judgment','role','output_citation','document_support','counterevidence','missing_link','ambiguity'}
   assert isinstance(a['claim_id'],str) and a['claim_id'].strip() and a['claim_id'] not in ids;ids.add(a['claim_id'])
   for field in ['claim','missing_link','ambiguity']:assert isinstance(a[field],str) and a[field].strip()
   assert a['judgment'] in {'supported','contradicted','unsupported','ambiguous','not_applicable'}
   assert a['role'] in {'target','explanation'}
   cite=a['output_citation'];output_citation_count+=1
   assert set(cite)=={'start','end','quote'}
   assert type(cite['start']) is int and type(cite['end']) is int
   assert source['start']<=cite['start']<cite['end']<=source['end']
   assert op['answer'][cite['start']:cite['end']]==cite['quote']
   for kind in ['document_support','counterevidence']:
    assert isinstance(a[kind],list)
    for cite in a[kind]:
     doc_citation_count+=1
     assert set(cite)=={'document_index','start','end','quote'}
     assert type(cite['document_index']) is int and 1<=cite['document_index']<=5
     d=ip['documents'][cite['document_index']-1]
     assert type(cite['start']) is int and type(cite['end']) is int
     assert 0<=cite['start']<cite['end']<=len(d)
     assert d[cite['start']:cite['end']]==cite['quote']
   if a['judgment']=='supported': assert a['document_support']
   if a['judgment']=='contradicted': assert a['counterevidence']
 assert last==len(op['answer'])
 targets=[a for a in atoms if a['role']=='target']
 explanations=[a for a in atoms if a['role']=='explanation' and a['judgment']!='not_applicable']
 if row['gives_specific_target_answer']:
  assert targets and all(a['judgment']!='not_applicable' for a in targets)
  reduced=next(j for j in ['contradicted','unsupported','ambiguous','supported'] if any(a['judgment']==j for a in targets))
  assert row['target_claim_supported']==reduced
  assert row['withholding_matches_gap']=='not_applicable'
 else:
  assert not targets and row['target_claim_supported']=='not_applicable'
  assert row['withholding_matches_gap'] in {'supported','contradicted','unsupported','ambiguous'}
 reduced=('not_applicable' if not explanations else 'no' if any(a['judgment'] in {'unsupported','contradicted'} for a in explanations) else 'ambiguous' if any(a['judgment']=='ambiguous' for a in explanations) else 'yes')
 assert row['explanation_all_claims_supported']==reduced
assert log['output_packet_sha256']==sha('output_packet.json')
seal_time_present='input_review_completed_at' in seal and isinstance(seal['input_review_completed_at'],str)
if seal_time_present:
 assert r['sealed_input_review_completed_at']==context['sealed_input_review_completed_at']==seal['input_review_completed_at']
else:
 assert r['sealed_input_review_completed_at'] is None and context['sealed_input_review_completed_at'] is None
checks=['all 55 IDs preserved in order','all original unit IDs, source_span fields, offsets, quotes, and hashes preserved exactly','continuous mechanical unit coverage of all complete answers','all unit-level summary fields remain null',f'all {atom_count} manually authored atoms have unique item-local IDs and required fields','all output citations remain within their source units and match text exactly','all document citations have exact Unicode end-exclusive offsets','supported atoms have support and contradicted atoms have counterevidence','target applicability and precedence reductions','explanation summary reductions','all reading-log answer, question, document, and original-unit mappings','unchanged SHA256 for every recorded stage-1 file','sealed input-review SHA256 still matches']
report={'reviewer_id':r['reviewer_id'],'validated_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
 'validation_passed':seal_time_present,'semantic_review_complete_declared':True,'structural_and_citation_validation_passed':True,
 'input_seal_hash_verified':True,'stage1_files_unchanged':True,'stage1_files_verified':len(baseline),
 'seal_completion_timestamp_available':seal_time_present,
 'blocking_metadata_issues':[] if seal_time_present else ['input_seal.json omits input_review_completed_at; the required sealed_input_review_completed_at remains null rather than being invented or copied from a different source. A clarification request was sent.'],
 'counts':{'items_reviewed':55,'items_unreviewed':0,'original_units':unit_count,'atomic_claims':atom_count,
 'output_citations':output_citation_count,'document_citations':doc_citation_count,
 'specific_target_answers':sum(x['gives_specific_target_answer'] for x in r['items']),
 'no_specific_target_answer':sum(not x['gives_specific_target_answer'] for x in r['items']),
 'atomic_judgments':dict(judgments),'atomic_roles':dict(roles),
 'target_claim_supported':dict(Counter(x['target_claim_supported'] for x in r['items'])),
 'withholding_matches_gap':dict(Counter(x['withholding_matches_gap'] for x in r['items'])),
 'explanation_all_claims_supported':dict(Counter(x['explanation_all_claims_supported'] for x in r['items']))},
 'checks_passed':checks,'sealed_input_review_sha256':seal['input_review_sha256'],
 'claim_review_sha256':sha('claim_review.json'),
 'limitations':['Semantic correctness and full semantic coverage remain reviewer judgments, not consequences of byte/span validation.','No author comparison or independent approval was performed. Authorized answers were read only after the seal hash matched.','No stage-1 judgments or files were revised.']}
Path('output_validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
