"""User-operated, informed development-only frozen probe prefill; no generation or fit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import controlled_evidence_pilot as pilot
import evidence_experiment as e
import probe_input_shift as d
import probe_neutral_length_control_20261109 as neutral

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/qwen2.5-3b-new-controlled-probe-20261111-v1'
ART=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1'
SOURCE=ROOT/'runs/qwen2.5-3b-probe-support-expression-v1'
MODEL='/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct'
REFERENCE=ROOT/'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
PROBE_SHA='db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
require=pilot.require

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p): return neutral.digest(p)
def encoded(v): return neutral.json_bytes(v)
def identity(row,tokenizer): return neutral.identity(row,tokenizer)

def write_or_check(path, value, write):
    b=encoded(value)
    if path.exists(): require(path.read_bytes()==b,'frozen artifact differs: '+str(path))
    elif write:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:
            f.write(b); f.flush(); os.fsync(f.fileno())
    else: raise ValueError('missing frozen artifact: '+str(path))

def validate_pending(run, records, protocol_sha):
    attempts=run/'attempts'
    files=sorted(attempts.glob('*')) if attempts.exists() else []
    require(len(files)==len(records),'uncommitted or missing attempt; stop and preserve')
    require({p.name for p in files}=={f'{i:04d}.json' for i in range(len(records))},'attempt ordering differs')
    for i,rec in enumerate(records):
        require(load(attempts/f'{i:04d}.json')=={'index':i,'id':rec['id'],'protocol_sha256':protocol_sha},'attempt binding differs')
    features=run/'features'
    actual=set(features.glob('*')) if features.exists() else set()
    require(actual=={run/r['feature_file'] for r in records},'orphan or extra feature; stop and preserve')
    require(not (run/'states.json.tmp').exists(),'unfinished state write; stop and preserve')

def setup(write):
    from transformers import AutoTokenizer
    require(not (RUN/'last_failure.json').exists(),'failure marker exists; preserve run')
    material=load(ART/'materials.json'); review=load(ART/'author-review.json'); seal=load(ART/'material-seal.json')
    require(seal['materials_sha256']==digest(ART/'materials.json') and seal['review_sha256']==digest(ART/'author-review.json'),'review seal differs')
    require(seal['spec_sha256']==digest(ROOT/'prompts/new_controlled_probe_20261111_v1.json') and
            seal['new_probe_predictions_observed'] is False and seal['formal_labels'] is None,'author seal invalid')
    rows=material['rows']; ids=[r['id'] for r in rows]
    require(len(rows)==len(set(ids))==len(review['items'])==36,'scope differs')
    require([r['id'] for r in review['items']]==ids and all(
        x['status']=='informed_author_reference_not_independent_gold' and x['all_five_slots_checked'] is True
        and x['expression_pair']=='informed_author_assessment_preserves_target_relation' for x in review['items']), 'reference unresolved')
    old=load(SOURCE/'protocol.json'); source_state=load(SOURCE/'states.json')
    require(digest(SOURCE/'protocol.json')==source_state['protocol_sha256'],'old protocol differs')
    for name,expected in {**old['implementation_sha256'],**old['source_sha256']}.items():
        require(digest(ROOT/name)==expected,'prior frozen dependency differs: '+name)
    require(old['model']==MODEL and old['frozen_probe_layer']==28,'backbone or probe layer differs')
    require({k:e.version(k) for k in old['runtime_versions']}==old['runtime_versions'],'runtime version differs')
    ref=load(REFERENCE)
    require(ref['model']==MODEL and all(ref['model_files_sha256'][k]==v
            for k,v in old['backbone_signature']['model_files'].items()),'model reference differs')
    for name in old['backbone_signature']['model_files']:
        require(digest(Path(MODEL)/name)==ref['model_files_sha256'][name],'model metadata differs: '+name)
    probe, hashes, _=pilot.probe_resources(MODEL)
    require(hashes['runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl']==PROBE_SHA,'probe hash differs')
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    originals=load(SOURCE/'materials/inputs.json')
    bridges=[r for r in originals if r['id']=='support06_D1']
    matches=[r for r in source_state['records'] if r['id']=='support06_D1']
    require(len(bridges)==len(matches)==1,'bridge missing/duplicate')
    bridge=bridges[0]; bridge_record=matches[0]
    b=dict(id='bridge_support06_D1',original_id=bridge['original_id'],question_level=bridge['question_level'],
           document_level=bridge['document_level'],question=bridge['question'],docs=bridge['docs'],
           source={'base':str(SOURCE.relative_to(ROOT)),'record':bridge_record})
    baseline=d.source_state(b,tok,MODEL)
    old_prediction=d.prediction(probe,baseline)
    require(old_prediction['probe_pred']==bridge_record['probe_pred'] and all(
        abs(old_prediction['probe_probabilities'][k]-bridge_record['probe_probabilities'][k])<1e-9 for k in e.MODES),
        'old bridge prediction differs')
    full=[b]+rows
    identities={r['id']:identity(r,tok) for r in full}
    require(len(identities)==37 and max(x['input_tokens'] for x in identities.values())<=ref['context_tokens'],'scope/context differs')
    files=['scripts/new_controlled_probe_20261111.py','scripts/new_controlled_probe_materials_20261111.py',
           'scripts/verify_new_controlled_probe_materials_20261111.py','prompts/new_controlled_probe_20261111_v1.json',
           'docs/review/2026-11-11-new-controlled-exploration-v1/materials.json',
           'docs/review/2026-11-11-new-controlled-exploration-v1/author-review.json',
           'docs/review/2026-11-11-new-controlled-exploration-v1/material-seal.json']
    dependencies={**old['implementation_sha256'],**old['source_sha256'],**hashes}
    dependencies.update({str(p.relative_to(ROOT)):digest(p) for p in [REFERENCE,SOURCE/'protocol.json',SOURCE/'states.json',SOURCE/'materials/inputs.json']})
    dependencies.update({name:digest(ROOT/name) for name in files})
    plan={'schema_version':1,'task':'informed_controlled_development_not_confirmation','operator':'user','model':MODEL,
          'bridge_first':b['id'],'new_bases':6,'new_inputs':36,'new_forwards':37,'new_answers':0,'new_fits':0,
          'source_probe_sha256':PROBE_SHA,'dependencies':dict(sorted(dependencies.items())),
          'model_files_sha256':ref['model_files_sha256'],'runtime_versions':old['runtime_versions'],
          'identities':identities,'bridge_tolerances':{'max_layer_relative_l2':0.02,'max_probability_absolute_error':0.01},
          'held_out_380_access':False,'reference':'informed author assessment, not independent gold',
          'gate':'new user-operated exploratory path only; original v1 and E1-r1 unchanged',
          'analysis':'per base S/I/C A/B: 18 expression pairs, 12 S-I and 12 S-C; descriptive only'}
    write_or_check(RUN/'protocol.json',plan,write)
    write_or_check(RUN/'materials/inputs.json',full,write)
    return full, review, tok, probe, plan

def check_bridge(row,record,tok,probe,plan):
    actual=np.load(RUN/record['feature_file'],allow_pickle=False)
    err=d.bridge_error(actual,d.source_state(row,tok,MODEL),probe)
    require(all(err[k]<=limit for k,limit in plan['bridge_tolerances'].items()),'bridge failed: '+str(err))
    return err

def prefix(rows,tok,probe,plan):
    args=argparse.Namespace(run_dir=RUN,model=MODEL,smoke=True)
    records=d.cache(args,rows,probe,tok)
    validate_pending(RUN,records,digest(RUN/'protocol.json'))
    for row,record in zip(rows,records):
        require(identity(row,tok)==plan['identities'][row['id']],'token fingerprint differs')
        require(record.get('id')==row['id'],'record order differs')
    if records: check_bridge(rows[0],records[0],tok,probe,plan)
    return records

def collect(rows,tok,probe,plan):
    require(not (RUN/'last_failure.json').exists(),'failure marker exists; preserve run')
    records=prefix(rows,tok,probe,plan)
    if len(records)==len(rows): return records
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='0','launch with CUDA_VISIBLE_DEVICES=0')
    for name,expected in plan['model_files_sha256'].items():
        require(digest(Path(MODEL)/name)==expected,'model file SHA mismatch: '+name)
    pilot.s.assert_gpu_idle()
    import torch
    require(torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported(),'CUDA/bf16 unavailable')
    model=None
    try:
        model=e.load_model(MODEL)
        for i in range(len(records),len(rows)):
            row=rows[i]
            neutral.exclusive(RUN/'attempts'/f'{i:04d}.json',{'index':i,'id':row['id'],'protocol_sha256':digest(RUN/'protocol.json')})
            started=time.monotonic()
            inputs=e.encode(tok,d.prompt(row,tok),'chat',return_tensors='pt').to(model.device)
            torch.cuda.synchronize()
            with e.LastPromptCapture(model) as capture, torch.inference_mode():
                model.model(**inputs,use_cache=False,output_hidden_states=False)
            states=capture.array(); torch.cuda.synchronize(); del inputs
            d.validate_states(states,[36,2048])
            rel=f'features/{i:04d}.npy'; e.save_array(RUN/rel,states)
            record={k:row[k] for k in ('id','original_id','question_level','document_level')}
            recid=identity(row,tok)
            record.update(origin='new_forward',capture_phase='decoder_prefill_without_generation',
                prompt_sha256=recid['prompt_sha256'],input_tokens=recid['input_tokens'],
                feature_file=rel,feature_sha256=digest(RUN/rel),elapsed_seconds=time.monotonic()-started,
                completed_at=datetime.now(timezone.utc).isoformat(),**d.prediction(probe,states))
            if i==0: check_bridge(row,record,tok,probe,plan)
            records.append(record)
            e.repro.write_json(RUN/'states.json',{'protocol_sha256':digest(RUN/'protocol.json'),'records':records})
            print(f'prefill [{i+1}/37] {row["id"]}',flush=True)
    except Exception as error:
        if not (RUN/'last_failure.json').exists():
            neutral.exclusive(RUN/'last_failure.json',{'error':str(error),'records_committed':len(records)})
        raise
    finally:
        if model is not None: del model
        torch.cuda.empty_cache()
    return records

def report(rows,reviews,records):
    require(len(records)==37,'run incomplete')
    by={r['id']:r for r in records}; refs={r['id']:r for r in reviews['items']}
    table={}
    for row in rows[1:]:
        r=by[row['id']]; ref=refs[row['id']]
        table[(row['original_id'],row['document_level'],row['question_level'])]={'id':row['id'],
            'author_ref':ref['proposed_probe_class'],'pred':r['probe_pred'],'probs':r['probe_probabilities'],
            'tokens':r['input_tokens'],'matches_informed_author_ref':r['probe_pred']==ref['proposed_probe_class']}
    pairs=[]
    for base in dict.fromkeys(r['original_id'] for r in rows[1:]):
        for state in ('S','I','C'):
            a,b=table[base,state,'A'],table[base,state,'B']
            pairs.append({'type':'A-B','base':base,'state':state,'left':a,'right':b,
                          'class_same':a['pred']==b['pred']})
        for word in ('A','B'):
            for state in ('I','C'):
                a,b=table[base,'S',word],table[base,state,word]
                pairs.append({'type':'S-'+state,'base':base,'wording':word,'left':a,'right':b,
                    'probability_difference':{k:b['probs'][k]-a['probs'][k] for k in e.MODES}})
    require(len(pairs)==42,'pair count differs')
    return {'status':'technical_prefill_complete_informed_development_only','bases':6,'inputs':36,'bridge':1,
            'new_forwards':37,'new_answers':0,'new_fits':0,'independent_semantic_gold':False,'pairs':pairs}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',required=True,choices=['prepare','collect','verify'])
    parser.add_argument('--operator',choices=['user'])
    args=parser.parse_args()
    require(args.stage!='collect' or args.operator=='user','collection operator must be user')
    if args.stage!='prepare': require((RUN/'protocol.json').is_file(),'prepare not completed; no directory created')
    with e.legacy.run_lock(RUN):
        rows,reviews,tok,probe,plan=setup(write=args.stage=='prepare')
        if args.stage=='prepare':
            require(not (RUN/'states.json').exists(),'refuse prepare over records')
            validate_pending(RUN,[],digest(RUN/'protocol.json'))
            print(json.dumps({'status':'prepared_not_started','new_inputs':36,'bridge':1,'forwards':37,'GPU_accessed':False})); return
        records=collect(rows,tok,probe,plan) if args.stage=='collect' else prefix(rows,tok,probe,plan)
        result=report(rows,reviews,records)
        write_or_check(RUN/'report.json',result,args.stage=='collect')
        print(json.dumps({'status':result['status'],'pairs':len(result['pairs']),'new_forwards':37,'new_answers':0,'new_fits':0}))
if __name__=='__main__': main()
