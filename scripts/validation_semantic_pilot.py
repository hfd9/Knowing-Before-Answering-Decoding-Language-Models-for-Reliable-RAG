"""Fixed 30-input diagnostic review, sealed before model-output comparison."""

import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'runs/qwen2.5-3b-validation-semantic-pilot-2026-10-16-v1'
MODES={'answer','refuse','conflict','unknown'}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if path.exists():
        if path.read_text()!=text:
            raise ValueError(f'Refuse to change existing artifact: {path}')
        return
    path.write_text(text)


def prepare(base):
    source=ROOT/'runs/qwen2.5-3b-small/data/instances_val.jsonl'
    manifest=read(source.parent/'manifest.json')['splits']['val']
    if digest(source)!=manifest['sha256']:
        raise ValueError('Fixed validation hash mismatch')
    rows=[json.loads(line) for line in source.read_text().splitlines()]
    ids=list(dict.fromkeys(row['original_id'] for row in rows))
    selected=random.Random(42).sample(ids,10)
    chosen=[row for oid in selected for row in rows if row['original_id']==oid]
    if len(ids)!=95 or len(chosen)!=30:
        raise ValueError('Unexpected validation population')
    random.Random(43).shuffle(chosen)
    mapping={f'P{i:03d}':row['id'] for i,row in enumerate(chosen,1)}
    docs={}
    public=[]
    for key,row in zip(mapping,chosen):
        refs=[]
        for doc in row['docs']:
            ref='T'+hashlib.sha256(doc.encode()).hexdigest()[:16]
            if ref in docs and docs[ref]!=doc:
                raise ValueError('Document digest collision')
            docs[ref]=doc;refs.append(ref)
        public.append(dict(review_id=key,group_id=f'G{selected.index(row["original_id"])+1:02d}',
                           question=row['question'],doc_refs=refs))
    protocol=dict(schema_version=1,created_at='2026-10-16',task='30-input assistant semantic diagnosis before output reveal',
                  source_path=str(source.relative_to(ROOT)),source_sha256=digest(source),
                  sampling='Python random.Random(42).sample(first-occurrence original_id order,10); keep all3 configs; shuffle rows seed43',
                  selected_original_ids=selected,instances=30,base_questions=10,
                  reviewer='current_coordinating_assistant',
                  provenance='Project/history exposed; previously saw aggregate results and some output-ID diagnostics. Not independent, human or fully blind. No selected full model output intentionally loaded before input seal.',
                  rules=dict(answer='Every necessary premise supported by supplied text; no relevant incompatible assertion.',
                             refuse='At least one necessary premise missing; absence alone is not a factual negative.',
                             conflict='Two explicitly incompatible answer-relevant claims in same entity/time/property scope; may occur within one document.',
                             unknown='Question scope/identity/time or evidence too ambiguous for a definite mode. Do not force a mode.',
                             scope='Read complete question and all five documents. No outside facts or model outputs. Comparison/choice questions require the stated joint conditions.',
                             time='Respect explicit dates. Different times alone are not conflict; unresolved temporal question scope may be unknown.',
                             compatibility='Different people, roles, descriptions or multiple compatible categories do not establish conflict.',
                             citation='Exact original substrings with document slots. answer needs support; conflict needs both opposing claims, not necessarily distinct documents.',
                             disclosure='Input-only ordering reduces new output contamination but does not erase existing project/ID exposure.'),
                  script_sha256=digest(Path(__file__)))
    save_new(base/'protocol.json',protocol)
    save_new(base/'coordinator/mapping.json',mapping)
    save_new(base/'public/inputs.json',dict(records=public,documents=docs))
    protected=[source,ROOT/'runs/qwen2.5-3b-validation-evidence-audit-v4/drafts/predictions.json',
               ROOT/'runs/qwen2.5-3b-free-answer-study/annotations.csv']
    prior=ROOT/'runs/qwen2.5-3b-classification-prompt-validation-v3'
    protected += [prior/name/'predictions.json' for name in ['definitions','decision_order','illustrations']]
    protected += [ROOT/'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json']
    # Hashing opaque model output files binds later reveal without reading their records.
    save_new(base/'coordinator/protected_hashes.json',{str(p.relative_to(ROOT)):digest(p) for p in protected})
    print(json.dumps(dict(selected_original_ids=selected,records=30,unique_documents=len(docs),
                          unique_document_characters=sum(map(len,docs.values()))),ensure_ascii=False))


def validate_inputs(base,path):
    packet=read(base/'public/inputs.json')
    records={r['review_id']:r for r in packet['records']}
    values=read(path)
    if not isinstance(values,list) or len(values)!=30 or {r['review_id'] for r in values}!=set(records):
        raise ValueError('Need exactly all30 unique input ratings')
    for value in values:
        mode=value['semantic_mode']
        if mode not in MODES or not value['reason'].strip() or not value['required_facts']:
            raise ValueError('Mode, reason and required facts required')
        if value['all_five_documents_read'] is not True:
            raise ValueError('Complete document reading not attested')
        if not value['question_interpretation'].strip() or not value['reviewer'].strip():
            raise ValueError('Interpretation and reviewer required')
        row=records[value['review_id']]
        for cite in value['citations']:
            if type(cite['doc_id']) is not int or not 1<=cite['doc_id']<=5 or not cite['quote'].strip():
                raise ValueError('Invalid citation slot/text')
            doc=packet['documents'][row['doc_refs'][cite['doc_id']-1]]
            if cite['quote'] not in doc:
                raise ValueError(f'Quote absent: {value["review_id"]}: {cite["quote"]}')
        if mode=='answer' and not value['citations']:
            raise ValueError('Supported input needs a quote')
        if mode=='refuse' and not value['missing_facts']:
            raise ValueError('Insufficient input needs a missing premise')
        if mode=='conflict' and (len(value['conflicting_claims'])<2 or len(value['citations'])<2):
            raise ValueError('Conflict needs two claims and original supports')
    return values


def seal(base):
    path=base/'input_ratings.json'
    values=validate_inputs(base,path)
    target=base/'input_review_seal.json'
    if target.exists():
        if read(target)['input_ratings_sha256']!=digest(path):
            raise ValueError('Sealed inputs changed')
        return
    save_new(target,dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),input_ratings_sha256=digest(path),
                         protocol_sha256=digest(base/'protocol.json'),records=30,
                         mode_counts=dict(Counter(r['semantic_mode'] for r in values)),
                         provenance='Current assistant input-only review after project-level exposure; not independent gold.'))
    print(target)


def reveal(base):
    if not (base/'input_review_seal.json').exists():
        raise ValueError('Complete and seal all30 inputs before reveal')
    if read(base/'input_review_seal.json')['input_ratings_sha256']!=digest(base/'input_ratings.json'):
        raise ValueError('Input ratings changed after seal')
    for path,expected in read(base/'coordinator/protected_hashes.json').items():
        if digest(ROOT/path)!=expected:
            raise ValueError(f'Protected source changed: {path}')
    mapping=read(base/'coordinator/mapping.json')
    source=ROOT/'runs/qwen2.5-3b-small/data/instances_val.jsonl'
    rows={r['id']:r for r in map(json.loads,source.read_text().splitlines())}
    v4=read(ROOT/'runs/qwen2.5-3b-validation-evidence-audit-v4/drafts/predictions.json')['records']
    v4={r['id']:r for r in v4}
    sources={'legacy_chat8':ROOT/'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json'}
    sources.update({n:ROOT/f'runs/qwen2.5-3b-classification-prompt-validation-v3/{n}/predictions.json'
                    for n in ['definitions','decision_order','illustrations']})
    previous={}
    for name,path in sources.items():
        data=read(path);values=data['records'] if isinstance(data,dict) else data
        previous[name]={r['id']:r for r in values}
    revealed=[]
    for key,original in mapping.items():
        revealed.append(dict(review_id=key,id=original,original_id=rows[original]['original_id'],
                             published_mode=rows[original]['true_mode'],v4=v4[original],
                             previous={n:dict(pred_mode=values[original]['pred_mode'],raw_output=values[original]['raw_output'])
                                       for n,values in previous.items()}))
    save_new(base/'revealed/model_outputs.json',dict(input_ratings_sha256=digest(base/'input_ratings.json'),records=revealed))
    print('Revealed30 outputs after seal')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','seal-inputs','reveal'],required=True)
    parser.add_argument('--run_dir',type=Path,default=DEFAULT)
    args=parser.parse_args()
    base=args.run_dir.resolve()
    if args.stage=='prepare':prepare(base)
    elif args.stage=='seal-inputs':seal(base)
    else:reveal(base)


if __name__=='__main__':main()
