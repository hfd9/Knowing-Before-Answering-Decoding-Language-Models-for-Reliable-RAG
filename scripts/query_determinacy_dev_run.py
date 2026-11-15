#!/usr/bin/env python3
"""Frozen 72-item development run; GPU execution belongs to the user."""
import argparse
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import query_determinacy_dev_audit as audit
import query_determinacy_pilot as core
import query_determinacy_unattempted_v4 as verifier

ROOT=core.ROOT
RUN=ROOT/'runs/qwen2.5-3b-query-determinacy-development-v1'
ARCHIVE=ROOT/'docs/review/2026-11-15-query-determinacy-development-v1/manifest.json'
SCRIPTS=[Path(__file__).resolve(),Path(audit.__file__).resolve(),Path(core.__file__).resolve(),
         Path(verifier.__file__).resolve(),Path(verifier.base.__file__).resolve(),
         ROOT/'scripts/query_determinacy_material_audit.py']
LIMIT=384


def inputs():
    return {r['id']:r for r in map(json.loads,audit.MATERIAL.read_text(encoding='utf-8').splitlines())}


def ordered(rows):
    items=list(rows.values()); random.Random(19517).shuffle(items)
    rules=[lambda r:r['family']=='number' and r['query']=='same_yes' and r['condition']=='single_a',
           lambda r:r['family']=='category' and r['query']=='split' and r['condition']=='single_b',
           lambda r:r['family']=='number' and r['query']=='split' and r['condition']=='dual_sources',
           lambda r:r['family']=='category' and r['query']=='same_no' and r['condition']=='dual_alternatives']
    smoke=[next(r for r in items if rule(r)) for rule in rules]
    ids={r['id'] for r in smoke}
    if len(ids)!=4: raise ValueError('smoke items overlap')
    return smoke+[r for r in items if r['id'] not in ids]


def build_manifest():
    audit.audit(); rows=inputs(); order=ordered(rows)
    reference=json.loads(core.REFERENCE.read_text(encoding='utf-8'))
    if Path(reference['model'])!=core.MODEL: raise ValueError('model differs from reference')
    weights={name:core.file_hash(core.MODEL/name) for name in reference['model_files_sha256']}
    if weights!=reference['model_files_sha256']: raise ValueError('model files differ from reference')
    tok=core.tokenizer(); details=[]
    for row in order:
        text,ids=core.render(tok,row['prompt'])
        if len(ids)+LIMIT>reference['context_tokens']: raise ValueError('context too long')
        details.append({'id':row['id'],'prompt_sha256':core.digest(row['prompt'].encode()),
                        'rendered_sha256':core.digest(text.encode()),'token_ids_sha256':core.ids_hash(ids),
                        'input_tokens':len(ids)})
    eos=json.loads((core.MODEL/'generation_config.json').read_text())['eos_token_id']
    if not isinstance(eos,list):eos=[eos]
    return {'schema':'query_determinacy_development_v1','count':len(details),'smoke_count':4,'seed':19517,
            'items':details,'material_sha256':core.file_hash(audit.MATERIAL),
            'reference_sha256':core.file_hash(core.REFERENCE),
            'implementation_sha256':{str(p.relative_to(ROOT)):core.file_hash(p) for p in SCRIPTS},
            'model':str(core.MODEL),'model_files_sha256':weights,'versions':core.versions(),
            'generation':{'max_new_tokens':LIMIT,'do_sample':False,'num_beams':1,'dtype':'bfloat16',
                          'attention':'sdpa','use_cache':True,'eos_token_ids':eos},
            'failure_policy':'smoke failure stops; later technical failure saved and skipped without retry; structural failure stops',
            'semantic_review_completed':False}


def validate_files(manifest,include_weights=False):
    if manifest['versions']!=core.versions(): raise ValueError('versions changed')
    if core.file_hash(audit.MATERIAL)!=manifest['material_sha256']: raise ValueError('material changed')
    if core.file_hash(core.REFERENCE)!=manifest['reference_sha256']: raise ValueError('reference changed')
    for name,value in manifest['implementation_sha256'].items():
        if core.file_hash(ROOT/name)!=value: raise ValueError('implementation changed: '+name)
    for name,value in manifest['model_files_sha256'].items():
        if (include_weights or not name.endswith('.safetensors')) and core.file_hash(core.MODEL/name)!=value:
            raise ValueError('model changed: '+name)


def load_manifest():
    if ARCHIVE.is_symlink() or (RUN/'manifest.json').is_symlink() or ARCHIVE.read_bytes()!=(RUN/'manifest.json').read_bytes():
        raise ValueError('manifest differs from archive')
    manifest=json.loads(ARCHIVE.read_text())
    if manifest.get('schema')!='query_determinacy_development_v1' or manifest.get('count')!=72 or len(manifest['items'])!=72:
        raise ValueError('invalid manifest')
    return manifest


def receipt(index,item,status):
    return {'index':index,'id':item['id'],'technical_status':status,
            'attempt_sha256':core.file_hash(RUN/'attempts'/f'{index:03d}.json'),
            'record_sha256':core.file_hash(RUN/'records'/f'{index:03d}.json'),
            'decision':'preserve_unscored_do_not_retry'}


def read_state(manifest,tok,data):
    if {p.name for p in RUN.iterdir()}!={'manifest.json','run.lock','attempts','records','automatic_failures'}:
        raise ValueError('unexpected run directory contents')
    for name in ('attempts','records','automatic_failures'):
        if (RUN/name).is_symlink() or not (RUN/name).is_dir():raise ValueError('invalid directory')
    attempts=sorted((RUN/'attempts').iterdir()); records=sorted((RUN/'records').iterdir())
    receipts={p.name:p for p in (RUN/'automatic_failures').iterdir()}
    if len(attempts)!=len(records) or len(records)>manifest['count']:raise ValueError('unfinished or extra attempt')
    used=set(); failures=[]; verifier.RUN=RUN
    prompts={key:r['prompt'] for key,r in data.items()}
    for i,(ap,rp) in enumerate(zip(attempts,records)):
        name=f'{i:03d}.json'
        if ap.name!=name or rp.name!=name or ap.is_symlink() or rp.is_symlink():raise ValueError('invalid journal prefix')
        status=verifier.verify_new_record(i,manifest,tok,prompts)
        if status!='complete':
            if name not in receipts or receipts[name].is_symlink() or json.loads(receipts[name].read_text())!=receipt(i,manifest['items'][i],status):
                raise ValueError('technical failure receipt missing or changed')
            used.add(name);failures.append({'index':i,'id':manifest['items'][i]['id'],'status':status})
        elif name in receipts:raise ValueError('receipt attached to successful record')
    if set(receipts)!=used:raise ValueError('unexpected receipts')
    smoke_failed=any(x['index']<manifest['smoke_count'] for x in failures)
    return {'state':'blocked_smoke_failure' if smoke_failed else ('complete_unreviewed' if len(records)==manifest['count'] else 'valid_prefix'),
            'attempts':len(attempts),'records':len(records),'total':manifest['count'],
            'technical_failures':failures,'semantic_review_completed':False}


def prepare():
    if RUN.exists() or RUN.is_symlink() or ARCHIVE.exists(): raise ValueError('run or archive exists; do not overwrite')
    manifest=build_manifest()
    core.write_new(ARCHIVE,manifest)
    RUN.mkdir(mode=0o700)
    for name in ('attempts','records','automatic_failures'):(RUN/name).mkdir(mode=0o700)
    (RUN/'run.lock').touch(mode=0o600,exist_ok=False)
    core.write_new(RUN/'manifest.json',manifest)
    return {'state':'prepared_not_started','count':len(manifest['items']),'manifest_sha256':core.file_hash(ARCHIVE),
            'min_tokens':min(x['input_tokens'] for x in manifest['items']),
            'max_tokens':max(x['input_tokens'] for x in manifest['items'])}


def collect(manifest,tok,data):
    validate_files(manifest,include_weights=True)
    state=read_state(manifest,tok,data)
    if state['state']=='complete_unreviewed':return state
    if state['state']!='valid_prefix':raise ValueError('smoke failure: preserve and stop')
    core.verify_device()
    import torch
    from transformers import AutoModelForCausalLM,GenerationConfig
    model=AutoModelForCausalLM.from_pretrained(str(core.MODEL),local_files_only=True,dtype=torch.bfloat16,
                                               device_map={'':0},attn_implementation='sdpa').eval()
    model.requires_grad_(False)
    cfg=GenerationConfig(max_new_tokens=LIMIT,do_sample=False,num_beams=1,use_cache=True,
                         eos_token_id=manifest['generation']['eos_token_ids'],
                         bos_token_id=model.generation_config.bos_token_id,
                         pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)
    verifier.RUN=RUN
    prompts={key:r['prompt'] for key,r in data.items()}
    for i in range(state['records'],manifest['count']):
        item=manifest['items'][i]; _,ids=core.render(tok,prompts[item['id']])
        if core.ids_hash(ids)!=item['token_ids_sha256']:raise ValueError('input token mismatch')
        ap=RUN/'attempts'/f'{i:03d}.json'
        core.write_new(ap,{'index':i,'id':item['id'],'manifest_sha256':core.file_hash(RUN/'manifest.json')})
        input_ids=torch.tensor([ids],dtype=torch.long,device='cuda:0'); torch.cuda.synchronize(); start=time.monotonic()
        with torch.inference_mode():
            output=model.generate(input_ids=input_ids,attention_mask=torch.ones_like(input_ids),generation_config=cfg,logits_to_keep=1)
        torch.cuda.synchronize();elapsed=time.monotonic()-start
        if output.ndim!=2 or output.shape[0]!=1 or output[0,:len(ids)].tolist()!=ids:raise ValueError('invalid output prefix')
        tokens=output[0,len(ids):].tolist()
        record={'index':i,'id':item['id'],'attempt_sha256':core.file_hash(ap),'generated_token_ids':tokens,
                'generated_token_ids_sha256':core.ids_hash(tokens),'output':tok.decode(tokens,skip_special_tokens=True),
                'elapsed_seconds':elapsed,'completed_at':datetime.now(timezone.utc).isoformat()}
        core.write_new(RUN/'records'/f'{i:03d}.json',record)
        status=verifier.verify_new_record(i,manifest,tok,prompts)
        if status!='complete':core.write_new(RUN/'automatic_failures'/f'{i:03d}.json',receipt(i,item,status))
        print(json.dumps({'processed':i+1,'total':manifest['count'],'technical_status':status}),flush=True)
        if status!='complete' and i<manifest['smoke_count']:raise ValueError('technical failure during smoke')
    return read_state(manifest,tok,data)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('prepare','inspect','collect'))
    args=parser.parse_args()
    try:
        if args.stage=='prepare':result=prepare()
        else:
            core.RUN=RUN
            with core.locked():
                manifest=load_manifest();validate_files(manifest)
                tok=core.tokenizer();data=inputs()
                result=collect(manifest,tok,data) if args.stage=='collect' else read_state(manifest,tok,data)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve run, do not delete or retry attempts',file=sys.stderr);raise SystemExit(2) from error


if __name__=='__main__':main()
