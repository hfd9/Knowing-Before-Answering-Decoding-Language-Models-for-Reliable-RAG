"""User-operated fixed-probe prefill for matched-token neutral suffix controls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import probe_input_shift as d
import controlled_evidence_pilot as pilot
import controlled_evidence_materials as materials
import evidence_experiment as e

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runs/qwen2.5-3b-probe-support-expression-v1'
RUN = ROOT / 'runs/qwen2.5-3b-probe-neutral-length-control-20261109-v1'
SPEC = ROOT / 'prompts/probe_neutral_length_control_20261109.json'
REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
MODEL = '/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct'
SELF = 'scripts/probe_neutral_length_control_20261109.py'
PROBE_SHA = 'db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
require = materials.require


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode('utf-8')


def exclusive(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(json_bytes(value))
        f.flush()
        os.fsync(f.fileno())


def identity(row, tokenizer):
    text = d.prompt(row, tokenizer)
    tokens = e.encode(tokenizer, text, 'chat')['input_ids']
    return {'prompt_sha256': e.text_hash(text), 'input_tokens': len(tokens),
            'input_token_ids_sha256': hashlib.sha256(json.dumps(tokens).encode()).hexdigest()}


def build_rows(spec, originals, saved, tokenizer):
    require(spec['negative_bases']==['val_14','val_3','val_31','val_28','val_17','val_13'], 'base scope differs')
    require(spec['wordings']==['D','P'] and spec['new_neutral_inputs']==12 and spec['max_new_forwards']==13, 'planned scope differs')
    require(spec['new_generated_answers']==0 and spec['new_fits']==0 and spec['held_out_380_access'] is False, 'scope not permitted')
    by = {(r['original_id'],r['cell']):r for r in originals}
    records = {r['id']:r for r in saved}
    require(len(by)==len(originals)==50 and len(records)==len(saved)==50, 'source duplicates or missing')
    rows=[]; comparisons=[]
    bridge = next(r for r in originals if r['id']==spec['bridge_source_id'])
    rows.append(dict(id='bridge_'+bridge['id'], original_id=bridge['original_id'],
                     question_level=bridge['question_level'], document_level=bridge['document_level'],
                     question=bridge['question'], docs=bridge['docs'],
                     source={'base':str(SOURCE.relative_to(ROOT)), 'record':records[bridge['id']]}))
    for base in spec['negative_bases']:
        suffix=spec['suffixes'][base]
        require(suffix.startswith('Archive note: ') and ' not ' not in suffix.lower() and ' no ' not in suffix.lower(), 'invalid neutral note')
        for wording in spec['wordings']:
            positive, negative = by[base,wording+'0'],by[base,wording+'1']
            require(positive['question']==negative['question'], 'question changed')
            changed=[i for i in range(5) if positive['docs'][i]!=negative['docs'][i]]
            require(len(changed)==2, 'expected two edited target docs')
            original_suffixes=[]
            docs=list(positive['docs'])
            for i in changed:
                prefix=positive['docs'][i]+' '
                require(negative['docs'][i].startswith(prefix), 'negative is not an appended suffix')
                original_suffixes.append(negative['docs'][i][len(prefix):])
                docs[i] += ' '+suffix
            require(original_suffixes[0]==original_suffixes[1], 'negative suffix differs between target docs')
            row={'id':f'neutral_{base}_{wording}', 'original_id':base,
                 'question_level':positive['question_level'], 'document_level':wording+'N',
                 'question':positive['question'], 'docs':docs, 'source':None}
            p_id,n_id=identity(positive,tokenizer),identity(negative,tokenizer)
            neutral_id=identity(row,tokenizer)
            require(p_id['prompt_sha256']==records[positive['id']]['prompt_sha256'], 'positive prompt mismatch')
            require(n_id['prompt_sha256']==records[negative['id']]['prompt_sha256'], 'negative prompt mismatch')
            require(p_id['input_tokens']==records[positive['id']]['input_tokens'], 'positive token mismatch')
            require(n_id['input_tokens']==records[negative['id']]['input_tokens'], 'negative token mismatch')
            require(neutral_id['input_tokens']==n_id['input_tokens'], 'neutral and negative token counts differ')
            rows.append(row)
            comparisons.append({'base':base,'wording':wording,'positive_id':positive['id'],
                                'negative_id':negative['id'],'neutral_id':row['id'],
                                'positive_identity':p_id,'negative_identity':n_id,'neutral_identity':neutral_id,
                                'changed_document_slots':[i+1 for i in changed],
                                'negative_suffix':original_suffixes[0], 'neutral_suffix':suffix})
    require(len(rows)==13 and len(comparisons)==12, 'incorrect planned rows')
    return rows, comparisons, records


def setup(write):
    from transformers import AutoTokenizer
    spec=read(SPEC); old=read(SOURCE/'protocol.json'); old_state=read(SOURCE/'states.json')
    require(digest(SOURCE/'protocol.json')==old_state['protocol_sha256'], 'source protocol mismatch')
    for name, expected in {**old['implementation_sha256'],**old['source_sha256']}.items():
        require(digest(ROOT/name)==expected, 'frozen source differs: '+name)
    require(old['model']==MODEL and old['frozen_probe_layer']==28, 'source model/probe layer mismatch')
    require({k:e.version(k) for k in old['runtime_versions']}==old['runtime_versions'], 'runtime version mismatch')
    ref=read(REFERENCE)
    require(ref['model']==MODEL and all(ref['model_files_sha256'][k]==v
            for k,v in old['backbone_signature']['model_files'].items()), 'model reference mismatch')
    for name in old['backbone_signature']['model_files']:
        require(digest(Path(MODEL)/name)==ref['model_files_sha256'][name], 'model metadata mismatch: '+name)
    probe, probe_hashes, _ = pilot.probe_resources(MODEL)
    require(probe_hashes['runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl']==PROBE_SHA, 'probe hash mismatch')
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    originals=read(SOURCE/'materials/inputs.json')
    rows, comparisons, saved=build_rows(spec,originals,old_state['records'],tokenizer)
    require(all(identity(r,tokenizer)['input_tokens']<=ref['context_tokens'] for r in rows), 'context exceeded')
    for cmp in comparisons:
        for source_id in (cmp['positive_id'],cmp['negative_id']):
            rec=saved[source_id]; state=np.load(SOURCE/rec['feature_file'],allow_pickle=False)
            d.validate_states(state,[36,2048])
            require(digest(SOURCE/rec['feature_file'])==rec['feature_sha256'], 'old feature hash differs')
            pred=d.prediction(probe,state)
            require(pred['probe_pred']==rec['probe_pred'] and all(abs(pred['probe_probabilities'][k]-rec['probe_probabilities'][k])<1e-9 for k in e.MODES), 'old prediction mismatch')
    dependencies={**old['implementation_sha256'],**old['source_sha256']}
    dependencies.update({str(p.relative_to(ROOT)):digest(p) for p in [SPEC,REFERENCE,SOURCE/'protocol.json',SOURCE/'states.json',SOURCE/'materials/inputs.json',ROOT/SELF]})
    dependencies.update(probe_hashes)
    plan={'schema_version':1, 'task':spec['task'], 'model':MODEL, 'operator':'user',
          'input_rows':len(rows),'new_forwards':13, 'new_answers':0,'new_fits':0,
          'source_probe_sha256':PROBE_SHA, 'dependencies':dict(sorted(dependencies.items())),
          'model_files_sha256':ref['model_files_sha256'], 'runtime_versions':old['runtime_versions'],
          'identities':{r['id']:identity(r,tokenizer) for r in rows},
          'bridge_tolerances':spec['tolerances'], 'held_out_380_access':False,
          'exposure':spec['exposure'], 'analysis':spec['primary_comparison']}
    frozen={'protocol.json':plan,'materials/inputs.json':rows,'materials/comparisons.json':comparisons}
    for name,value in frozen.items():
        path=RUN/name; encoded=json_bytes(value)
        if write:
            if path.exists(): require(path.read_bytes()==encoded,'refuse to overwrite frozen material: '+name)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(encoded)
        else:
            require(path.read_bytes()==encoded,'frozen material differs: '+name)
    return spec,rows,comparisons,saved,tokenizer,probe,plan


def checked_prefix(rows, tokenizer, probe):
    args=argparse.Namespace(run_dir=RUN,model=MODEL,smoke=True)
    records=d.cache(args,rows,probe,tokenizer)
    protocol_sha=digest(RUN/'protocol.json')
    attempts=RUN/'attempts'
    files=sorted(attempts.glob('*.json')) if attempts.exists() else []
    require(len(files)==len(records), 'uncommitted or missing attempt; stop and preserve run')
    require({p.name for p in files}=={f'{i:04d}.json' for i in range(len(records))}, 'attempt ordering differs')
    for i,(row,record) in enumerate(zip(rows,records)):
        require(read(attempts/f'{i:04d}.json')=={'index':i,'id':row['id'],'protocol_sha256':protocol_sha}, 'attempt binding differs')
    features=RUN/'features'
    existing=set(features.glob('*')) if features.exists() else set()
    require(existing=={RUN/r['feature_file'] for r in records}, 'orphan/extra feature; stop and preserve run')
    if records:
        check_bridge(rows[0],records[0],tokenizer,probe)
    return records


def check_bridge(row, record, tokenizer, probe):
    actual=np.load(RUN/record['feature_file'],allow_pickle=False)
    baseline=d.source_state(row,tokenizer,MODEL)
    err=d.bridge_error(actual,baseline,probe)
    tol=read(SPEC)['tolerances']
    require(all(err[k]<=tol[k] for k in tol), 'bridge failed: '+str(err))
    return err


def check_weights(plan):
    for name,expected in plan['model_files_sha256'].items():
        require(digest(Path(MODEL)/name)==expected, 'model file SHA mismatch: '+name)


def collect(rows, comparisons, saved, tokenizer, probe, plan):
    require(not (RUN/'last_failure.json').exists(), 'failure marker exists; stop and preserve run')
    records=checked_prefix(rows,tokenizer,probe)
    if len(records)==len(rows):
        return records
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='0', 'launch with CUDA_VISIBLE_DEVICES=0')
    check_weights(plan)
    pilot.s.assert_gpu_idle()
    import torch
    require(torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported(), 'CUDA/bf16 unavailable')
    model=e.load_model(MODEL)
    try:
        for i in range(len(records),len(rows)):
            row=rows[i]
            exclusive(RUN/'attempts'/f'{i:04d}.json',{'index':i,'id':row['id'],'protocol_sha256':digest(RUN/'protocol.json')})
            started=time.monotonic()
            inputs=e.encode(tokenizer,d.prompt(row,tokenizer),'chat',return_tensors='pt').to(model.device)
            torch.cuda.synchronize()
            with e.LastPromptCapture(model) as capture, torch.inference_mode():
                model.model(**inputs,use_cache=False,output_hidden_states=False)
            states=capture.array(); torch.cuda.synchronize(); del inputs
            d.validate_states(states,[36,2048])
            rel=f'features/{i:04d}.npy'
            e.save_array(RUN/rel,states)
            record={k:row[k] for k in ['id','original_id','question_level','document_level']}
            record.update(origin='new_forward',capture_phase='decoder_prefill_without_generation',
                          prompt_sha256=identity(row,tokenizer)['prompt_sha256'],input_tokens=identity(row,tokenizer)['input_tokens'],
                          feature_file=rel,feature_sha256=digest(RUN/rel),elapsed_seconds=time.monotonic()-started,
                          completed_at=datetime.now(timezone.utc).isoformat(),**d.prediction(probe,states))
            if i==0:
                check_bridge(row,record,tokenizer,probe)
            records.append(record)
            e.repro.write_json(RUN/'states.json',{'protocol_sha256':digest(RUN/'protocol.json'),'records':records})
            print(f'prefill [{i+1}/13] {row["id"]}',flush=True)
    except Exception as error:
        if not (RUN/'last_failure.json').exists():
            exclusive(RUN/'last_failure.json',{'error':str(error),'records_committed':len(records)})
        raise
    finally:
        del model
        torch.cuda.empty_cache()
    return records


def report(comparisons,saved,records):
    by={r['id']:r for r in records}
    pairs=[]
    for x in comparisons:
        positive=saved[x['positive_id']]; negative=saved[x['negative_id']]; neutral=by[x['neutral_id']]
        pairs.append({'base':x['base'],'wording':x['wording'],
                      'positive_id':x['positive_id'],'negative_id':x['negative_id'],'neutral_id':x['neutral_id'],
                      'negative_tokens':x['negative_identity']['input_tokens'],'neutral_tokens':x['neutral_identity']['input_tokens'],
                      'positive_pred':positive['probe_pred'],'negative_pred':negative['probe_pred'],'neutral_pred':neutral['probe_pred'],
                      'positive_probabilities':positive['probe_probabilities'],'negative_probabilities':negative['probe_probabilities'],
                      'neutral_probabilities':neutral['probe_probabilities'],
                      'negative_minus_neutral_conflict':negative['probe_probabilities']['conflict']-neutral['probe_probabilities']['conflict']})
    return {'status':'technical_prefill_complete_exposed_development_only','pairs':pairs,
            'new_forwards':13,'new_answers':0,'new_fits':0,'semantic_gold':False,
            'interpretation':read(SPEC)['interpretation']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',required=True,choices=['prepare','collect','verify'])
    parser.add_argument('--operator',choices=['user'])
    args=parser.parse_args()
    require(args.stage!='collect' or args.operator=='user', 'collection operator must be user')
    with e.legacy.run_lock(RUN):
        spec,rows,comparisons,saved,tokenizer,probe,plan=setup(write=args.stage=='prepare')
        if args.stage=='prepare':
            print(json.dumps({'status':'prepared_not_started','inputs':len(rows),'new_forwards':13,'GPU_accessed':False}))
            return
        if args.stage=='collect':
            records=collect(rows,comparisons,saved,tokenizer,probe,plan)
        else:
            require(not (RUN/'last_failure.json').exists(), 'failure marker exists')
            records=checked_prefix(rows,tokenizer,probe)
        require(len(records)==13,'run incomplete')
        result=report(comparisons,saved,records)
        path=RUN/'report.json'
        if args.stage=='collect':
            if path.exists(): require(path.read_bytes()==json_bytes(result), 'existing report differs')
            else: path.write_bytes(json_bytes(result))
        else:
            require(path.read_bytes()==json_bytes(result),'report replay differs')
        print(json.dumps({'status':result['status'],'pairs':len(result['pairs']),'new_forwards':13,'new_answers':0,'new_fits':0}))


if __name__=='__main__':
    main()
