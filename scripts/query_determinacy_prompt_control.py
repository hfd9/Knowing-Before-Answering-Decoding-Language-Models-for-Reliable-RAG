#!/usr/bin/env python3
"""Prepare and collect paired, exposed prompt controls on the prior 72 items."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import query_determinacy_dev_audit as old_audit
import query_determinacy_dev_run as base

ROOT=base.ROOT
DIR=ROOT/'docs/review/2026-11-15-query-determinacy-prompt-control-v1'
MATERIAL=DIR/'material.jsonl'
ARCHIVE=DIR/'manifest.json'
RUN=ROOT/'runs/qwen2.5-3b-query-determinacy-prompt-control-v1'
OLD_MATERIAL=old_audit.MATERIAL
OLD_SUFFIX='请简短回答；如无法唯一确定，请说明。'
SUFFIXES={'plain':'请简短回答。',
          'decompose':'请逐一判断题设允许的每个可能值对问题的答案，再给出最终结论。'}


def rows():
    old_audit.audit(OLD_MATERIAL)
    original=[json.loads(x) for x in OLD_MATERIAL.read_text(encoding='utf-8').splitlines()]
    output=[]
    for row in original:
        if not row['prompt'].endswith(OLD_SUFFIX):raise ValueError('unexpected original prompt')
        for name,suffix in SUFFIXES.items():
            item=dict(row);item['source_id']=item['id'];item['id']=item['id']+'__'+name
            item['instruction_variant']=name
            item['prompt']=row['prompt'][:-len(OLD_SUFFIX)]+suffix
            output.append(item)
    return output


def prepare_material():
    generated=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows())
    if MATERIAL.exists():
        if MATERIAL.read_text(encoding='utf-8')!=generated:raise ValueError('existing material differs')
    else:
        with MATERIAL.open('x',encoding='utf-8') as f:f.write(generated)
    return {'inputs':len(rows()),'status':'material_verified'}


def inputs():
    expected=rows();observed=[json.loads(x) for x in MATERIAL.read_text(encoding='utf-8').splitlines()]
    if observed!=expected or len(observed)!=144 or len({r['id'] for r in observed})!=144:
        raise ValueError('prompt-control material does not match fixed transformation')
    return {r['id']:r for r in observed}


def build_manifest():
    data=inputs();ordered=base.ordered(data)
    reference=json.loads(base.core.REFERENCE.read_text(encoding='utf-8'))
    if Path(reference['model'])!=base.core.MODEL:raise ValueError('model reference mismatch')
    weights={name:base.core.file_hash(base.core.MODEL/name) for name in reference['model_files_sha256']}
    if weights!=reference['model_files_sha256']:raise ValueError('model files changed')
    tok=base.core.tokenizer();items=[]
    for row in ordered:
        rendered,ids=base.core.render(tok,row['prompt'])
        if len(ids)+base.LIMIT>reference['context_tokens']:raise ValueError('context too long')
        items.append({'id':row['id'],'prompt_sha256':base.core.digest(row['prompt'].encode()),
                      'rendered_sha256':base.core.digest(rendered.encode()),'token_ids_sha256':base.core.ids_hash(ids),
                      'input_tokens':len(ids)})
    eos=json.loads((base.core.MODEL/'generation_config.json').read_text())['eos_token_id']
    if not isinstance(eos,list):eos=[eos]
    scripts=base.SCRIPTS+[Path(__file__).resolve()]
    return {'schema':'query_determinacy_prompt_control_v1','count':len(items),'smoke_count':4,'seed':19517,
            'items':items,'material_sha256':base.core.file_hash(MATERIAL),
            'reference_sha256':base.core.file_hash(base.core.REFERENCE),
            'implementation_sha256':{str(p.relative_to(ROOT)):base.core.file_hash(p) for p in scripts},
            'model':str(base.core.MODEL),'model_files_sha256':weights,'versions':base.core.versions(),
            'generation':{'max_new_tokens':base.LIMIT,'do_sample':False,'num_beams':1,'dtype':'bfloat16',
                          'attention':'sdpa','use_cache':True,'eos_token_ids':eos},
            'failure_policy':'smoke failure stops; later technical failure saved and skipped without retry; structural failure stops',
            'semantic_review_completed':False}


def prepare():
    if RUN.exists() or RUN.is_symlink() or ARCHIVE.exists():raise ValueError('run or archive exists')
    prepare_material();manifest=build_manifest();base.core.write_new(ARCHIVE,manifest)
    RUN.mkdir(mode=0o700)
    for name in ('attempts','records','automatic_failures'):(RUN/name).mkdir(mode=0o700)
    (RUN/'run.lock').touch(mode=0o600,exist_ok=False);base.core.write_new(RUN/'manifest.json',manifest)
    return {'state':'prepared_not_started','count':len(manifest['items']),
            'manifest_sha256':base.core.file_hash(ARCHIVE),'min_tokens':min(x['input_tokens'] for x in manifest['items']),
            'max_tokens':max(x['input_tokens'] for x in manifest['items'])}


def load_manifest():
    if ARCHIVE.is_symlink() or (RUN/'manifest.json').is_symlink() or ARCHIVE.read_bytes()!=(RUN/'manifest.json').read_bytes():
        raise ValueError('manifest differs from archive')
    manifest=json.loads(ARCHIVE.read_text())
    if manifest.get('schema')!='query_determinacy_prompt_control_v1' or manifest.get('count')!=144 or len(manifest['items'])!=144:
        raise ValueError('invalid manifest')
    return manifest


def configure():
    base.RUN=RUN
    base.core.RUN=RUN
    old_audit.MATERIAL=MATERIAL


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('material','prepare','inspect','collect'))
    args=parser.parse_args()
    try:
        if args.stage=='material':result=prepare_material()
        elif args.stage=='prepare':result=prepare()
        else:
            data=inputs();configure()
            with base.core.locked():
                manifest=load_manifest();base.validate_files(manifest)
                tok=base.core.tokenizer()
                result=base.collect(manifest,tok,data) if args.stage=='collect' else base.read_state(manifest,tok,data)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve run, do not delete or retry attempts',file=sys.stderr);raise SystemExit(2) from error


if __name__=='__main__':main()
