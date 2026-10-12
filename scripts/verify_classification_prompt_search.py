import argparse
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import classification_prompt_search as s
from transformers import AutoTokenizer
MODES=['answer','refuse','conflict']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def parse(raw):
    m=re.fullmatch(r'(answer|refuse|conflict)[.!]?',raw.strip(),re.IGNORECASE)
    return m.group(1).lower() if m else None
def measure(rows, records):
    matrix=[[0]*4 for _ in range(3)]
    for row,r in zip(rows,records):
        matrix[MODES.index(row['true_mode'])][MODES.index(r['pred_mode']) if r['pred_mode'] in MODES else 3]+=1
    support=[sum(row) for row in matrix];predicted=[sum(matrix[i][j] for i in range(3)) for j in range(3)]
    classes={m:dict(precision=matrix[i][i]/predicted[i] if predicted[i] else 0.,recall=matrix[i][i]/support[i],f1=2*matrix[i][i]/(support[i]+predicted[i]),support=support[i],correct=matrix[i][i]) for i,m in enumerate(MODES)}
    return dict(correct=sum(matrix[i][i] for i in range(3)),accuracy=sum(matrix[i][i] for i in range(3))/len(rows),macro_f1=sum(v['f1'] for v in classes.values())/3,confusion_matrix=matrix,per_class=classes,classification_false_answer_rate=(matrix[1][0]+matrix[2][0])/(support[1]+support[2]),parse_coverage=1-sum(row[3] for row in matrix)/len(rows),strict_format_pass_rate=sum(parse(r['raw_output']) is not None for r in records)/len(rows),refuse_to_answer_count=matrix[1][0],conflict_to_answer_count=matrix[2][0],hit_output_limit_count=sum(r['hit_output_limit'] for r in records),empty_output_count=sum(not r['raw_output'].strip() for r in records))
def selection(metrics,config):
    policy=config['selection'];eligible=[]
    for name in config['candidate_order']:
        v=metrics[name]
        if v['parse_coverage']>=policy['minimum_parse_coverage'] and v['strict_format_pass_rate']>=policy['minimum_strict_format_rate'] and min(x['recall'] for x in v['per_class'].values())>=policy['minimum_recall_each_class'] and v['classification_false_answer_rate']<=policy['maximum_classification_false_answer_rate']:eligible.append(name)
    ordered=sorted(eligible or config['candidate_order'],key=lambda n:(-metrics[n]['macro_f1'],metrics[n]['classification_false_answer_rate'],-min(x['recall'] for x in metrics[n]['per_class'].values()),config['candidate_order'].index(n)))
    return dict(eligible_candidates=eligible,selected_candidate=ordered[0] if eligible else None,diagnostic_best_candidate=ordered[0],status='candidate_selected_for_later_confirmation' if eligible else 'no_qualified_baseline')
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
config=s.e.read_json(s.PROMPTS)
full=ROOT/'runs/qwen2.5-3b-classification-prompt-validation-v3'
proto=s.e.read_json(full/'protocol.json')
tokenizer=AutoTokenizer.from_pretrained(proto['model'],local_files_only=True)
result=dict(checked_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status='read_only_snapshot',runs={},no_gpu_or_model_loaded=True,metric_recount='Independent Python counts and regex parser; protocol/cache renderer and deterministic bootstrap checked with original helpers.')
for name in ['qwen2.5-3b-classification-prompt-validation-smoke-v3','qwen2.5-3b-classification-prompt-validation-v3']:
    d=ROOT/'runs'/name;p=s.e.read_json(d/'protocol.json');ph=digest(d/'protocol.json')
    a=argparse.Namespace(reference=Path(p['reference']),model=p['model'],baseline=ROOT/'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json',run_dir=d,limit_questions=3 if p['smoke'] else None)
    rows,spec=s.sources(a)
    assert p==s.protocol(a,rows,spec,config),'Rebuilt frozen protocol differs'
    gate=s.e.read_json(d/'review_gate_snapshot.json')
    for f,h in gate['ratings_sha256'].items():assert digest(ROOT/f)==h,f
    baseline=s.baseline(a,rows,tokenizer);methods={'legacy_chat8':baseline};counts={};hashes={};stats={}
    for candidate in config['candidate_order']:
        path=d/candidate/'predictions.json'
        records=s.cached(path,dict(protocol_sha256=ph,candidate=candidate,split='val'),rows,config['instructions'][candidate],tokenizer)
        for row,r in zip(rows,records):
            assert r['original_id']==row['original_id']
            assert parse(r['raw_output'].strip().splitlines()[0] if r['raw_output'].strip() else '')==r['pred_mode']
            assert (parse(r['raw_output']) is not None)==r['strict_format_pass']
            assert len(s.e.encode(tokenizer,s.render(row,config['instructions'][candidate],tokenizer),'chat')['input_ids'])==r['input_tokens']
            assert not r['hit_output_limit'] or r['generated_tokens']==8
        methods[candidate]=records;counts[candidate]=len(records)
        if path.exists():hashes[str(path.relative_to(ROOT))]=digest(path)
        if records:stats[candidate]=dict(saved=len(records),first_saved=records[0]['completed_at'],last_saved=records[-1]['completed_at'],generation_seconds=sum(r['elapsed_seconds'] for r in records),max_peak_allocated_gib=max(r['peak_allocated_gib'] for r in records),prediction_counts=dict(Counter(r['pred_mode'] for r in records)))
    complete=all(v==len(rows) for v in counts.values())
    metrics={}
    for method,records in methods.items():
        if len(records)==len(rows):metrics[method]=measure(rows,records)
    reportpath=d/'reports/val.json';report=s.e.read_json(reportpath) if reportpath.exists() else None
    report_verified=False;bootstrap_verified=False
    if complete and report is not None:
        assert report['instances']==len(rows) and report['protocol_sha256']==ph
        for method,v in metrics.items():
            for key,value in v.items():assert report['methods'][method][key]==value,(name,method,key)
        if p['smoke']:assert report['selection']==dict(status='smoke_only_no_selection',selected_candidate=None)
        else:assert report['selection']==selection(metrics,config)
        for candidate in config['candidate_order']:
            assert report['paired_question_bootstrap'][candidate+'_minus_legacy_chat8']==s.e.bootstrap_pair(rows,methods[candidate],baseline)
        bootstrap_verified=report_verified=True
    result['runs'][name]=dict(instances_per_candidate=len(rows),counts=counts,generation_complete=complete,progress=s.e.read_json(d/'progress.json'),report_verified=report_verified,bootstrap_verified=bootstrap_verified,selection=report['selection'] if report else None,metrics=metrics,statistics=stats,predictions_sha256=hashes,protocol_sha256=ph,failure_file_exists=(d/'last_failure.json').exists(),code_model_data_protocol_rebuilt_and_equal=True,gate_fingerprints_verified=True)
    print(name,counts,'report_verified',report_verified,flush=True)
result['status']='verified_complete' if all(r['report_verified'] for r in result['runs'].values()) else 'running_snapshot_verified'
result['checked_at_end']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('snapshot',result['status'],result['checked_at_end'],flush=True)
