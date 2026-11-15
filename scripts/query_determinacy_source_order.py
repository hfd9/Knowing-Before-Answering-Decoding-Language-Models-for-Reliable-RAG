#!/usr/bin/env python3
"""Prepare targeted, exposed source-label and clause-order controls."""
import argparse
import json
from pathlib import Path
import random
import re
import subprocess
import sys

import query_determinacy_dev_run as base
import query_determinacy_fresh_audit as original

ROOT=base.ROOT
DIR=ROOT/'docs/review/2026-11-15-query-determinacy-source-order-v1'
MATERIAL=DIR/'material.jsonl'
ARCHIVE=DIR/'manifest.json'
RUN=ROOT/'runs/qwen2.5-3b-query-determinacy-source-order-v1'
PATTERN=re.compile(r'资料甲称(?P<subject>[^；。]+?)为(?P<first>[^；。]+)；资料乙称其为(?P<second>[^；。]+)。')


def transform():
    original.audit()
    rows=[json.loads(x) for x in original.MATERIAL.read_text(encoding='utf-8').splitlines()]
    selected=[r for r in rows if r['query']=='split' and r['condition']=='dual_sources' and r['instruction_variant']=='decompose']
    if len(selected)!=8:raise ValueError('expected eight original split sources')
    output=[]
    for row in selected:
        match=PATTERN.search(row['prompt'])
        if not match or len(PATTERN.findall(row['prompt']))!=1:raise ValueError('source clause shape changed')
        for variant in ('swap_labels','swap_order'):
            clause=match.group()
            if variant=='swap_labels':
                replacement=clause.replace('资料甲','资料临时').replace('资料乙','资料甲').replace('资料临时','资料乙')
            else:
                replacement=f"资料乙称{match['subject']}为{match['second']}；资料甲称其为{match['first']}。"
            item=dict(row);item['source_id']=row['id'];item['id']=row['id']+'__'+variant
            item['source_variant']=variant;item['prompt']=row['prompt'][:match.start()]+replacement+row['prompt'][match.end():]
            output.append(item)
    return output


def material():
    contents=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in transform())
    if MATERIAL.exists():
        if MATERIAL.read_text(encoding='utf-8')!=contents:raise ValueError('existing material changed')
    else:
        with MATERIAL.open('x',encoding='utf-8') as f:f.write(contents)


def inputs():
    data=[json.loads(x) for x in MATERIAL.read_text(encoding='utf-8').splitlines()]
    if data!=transform() or len(data)!=16 or len({r['id'] for r in data})!=16:raise ValueError('material mismatch')
    return {r['id']:r for r in data}


def ordered(data):
    rows=list(data.values());random.Random(8721).shuffle(rows)
    rules=[lambda r:r['family']=='number' and r['source_variant']=='swap_labels',
           lambda r:r['family']=='category' and r['source_variant']=='swap_labels',
           lambda r:r['family']=='number' and r['source_variant']=='swap_order',
           lambda r:r['family']=='category' and r['source_variant']=='swap_order']
    smoke=[next(r for r in rows if rule(r)) for rule in rules]; ids={r['id'] for r in smoke}
    if len(ids)!=4:raise ValueError('smoke collision')
    return smoke+[r for r in rows if r['id'] not in ids]


def build_manifest():
    rows=ordered(inputs());reference=json.loads(base.core.REFERENCE.read_text(encoding='utf-8'))
    if Path(reference['model'])!=base.core.MODEL:raise ValueError('model reference mismatch')
    weights={name:base.core.file_hash(base.core.MODEL/name) for name in reference['model_files_sha256']}
    if weights!=reference['model_files_sha256']:raise ValueError('model file mismatch')
    tok=base.core.tokenizer();items=[]
    for row in rows:
        text,ids=base.core.render(tok,row['prompt'])
        if len(ids)+base.LIMIT>reference['context_tokens']:raise ValueError('context too long')
        items.append({'id':row['id'],'prompt_sha256':base.core.digest(row['prompt'].encode()),
                      'rendered_sha256':base.core.digest(text.encode()),'token_ids_sha256':base.core.ids_hash(ids),
                      'input_tokens':len(ids)})
    eos=json.loads((base.core.MODEL/'generation_config.json').read_text())['eos_token_id']
    if not isinstance(eos,list):eos=[eos]
    scripts=base.SCRIPTS+[Path(__file__).resolve(),Path(original.__file__).resolve()]
    return {'schema':'query_determinacy_source_order_v1','count':16,'smoke_count':4,'seed':8721,'items':items,
            'material_sha256':base.core.file_hash(MATERIAL),'reference_sha256':base.core.file_hash(base.core.REFERENCE),
            'implementation_sha256':{str(p.relative_to(ROOT)):base.core.file_hash(p) for p in scripts},
            'model':str(base.core.MODEL),'model_files_sha256':weights,'versions':base.core.versions(),
            'generation':{'max_new_tokens':base.LIMIT,'do_sample':False,'num_beams':1,'dtype':'bfloat16',
                          'attention':'sdpa','use_cache':True,'eos_token_ids':eos},
            'failure_policy':'smoke failure stops; later technical failure saved and skipped without retry; structural failure stops',
            'semantic_review_completed':False}


def prepare():
    if RUN.exists() or RUN.is_symlink() or ARCHIVE.exists():raise ValueError('run or archive exists')
    material();manifest=build_manifest();base.core.write_new(ARCHIVE,manifest)
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
    if manifest.get('schema')!='query_determinacy_source_order_v1' or manifest.get('count')!=16 or len(manifest['items'])!=16:
        raise ValueError('invalid manifest')
    return manifest


def configure():
    base.RUN=RUN;base.core.RUN=RUN;base.audit.MATERIAL=MATERIAL


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('prepare','inspect','collect'))
    args=parser.parse_args()
    try:
        if args.stage=='prepare':result=prepare()
        else:
            data=inputs();configure()
            with base.core.locked():
                manifest=load_manifest();base.validate_files(manifest);tok=base.core.tokenizer()
                result=base.collect(manifest,tok,data) if args.stage=='collect' else base.read_state(manifest,tok,data)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve run, do not delete or retry attempts',file=sys.stderr);raise SystemExit(2) from error


if __name__=='__main__':main()
