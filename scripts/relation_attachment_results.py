"""Replay sealed handwritten48 behavior judgments and the frozen TA-OA contrast.

Stdlib/CPU only; no automatic semantic scoring, model, probe, fit or new sampling.
All outputs are separate from the original collection run and its blank templates.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
RUN='runs/qwen2.5-3b-relation-attachment-v1'
P='docs/records/2026-10-23-relation-attachment-results'
FIELDS=['has_substantive_target_answer','adopts_displayed_candidate_as_requested_target_value',
        'supported_target_answer','acknowledges_missing_target_attribute','claimed_evidence_supports_target']


def require(ok,message):
    if not ok:
        raise ValueError(message)


def read(name):
    return json.loads((ROOT/name).read_text())


def sha(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value,ensure_ascii=False,indent=2)+'\n'


def csv_text(rows,columns):
    out=io.StringIO(newline='')
    w=csv.DictWriter(out,fieldnames=columns)
    w.writeheader();w.writerows({k:r[k] for k in columns} for r in rows)
    return out.getvalue()


def preserved():
    old=read(P+'-preserved.json')
    for path,digest in old.items():
        require(sha(path)==digest,'Old path changed: '+path)
    expected=read(P+'-source-run-hashes.json')
    actual={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/RUN).rglob('*') if p.is_file() and p.name!='.run.lock'}
    require(actual==expected,'Original run set/bytes changed')
    return len(old),len(expected)


def quote(text,snippet=None,document_index=None):
    snippet=text if snippet is None else snippet
    require(bool(snippet) and text.count(snippet)==1,'Missing/ambiguous citation')
    start=text.index(snippet)
    result=dict(start=start,end=start+len(snippet),quote=snippet,
        text_sha256=hashlib.sha256(text.encode()).hexdigest())
    if document_index is not None:
        result['document_index']=document_index
    return result


def interval(value):
    require(value in ['yes','no','unknown'],'Invalid binary judgment')
    return {'yes':(1,1),'no':(0,0),'unknown':(0,1)}[value]


def rate(values):
    counts=Counter(values)
    require(set(counts)<={'yes','no','unknown'},'Invalid rate values')
    n=len(values)
    return dict(eligible=n,yes=counts['yes'],no=counts['no'],unknown=counts['unknown'],
        point=counts['yes']/n if n and not counts['unknown'] else None,
        identification_lower=counts['yes']/n if n else None,
        identification_upper=(counts['yes']+counts['unknown'])/n if n else None)


def group(rows):
    return dict(rows=len(rows),scenarios=len({r['scenario'] for r in rows}),
        fields={f:rate([r[f] for r in rows]) for f in FIELDS})


def compute():
    old_count,run_count=preserved()
    seal,manual=read(P+'-judgment-seal.json'),read(P+'-manual.json')
    require(seal['manual_sha256']==sha(P+'-manual.json')
            and seal['packet_sha256']==sha(RUN+'/behavior_review/packet.json'), 'Judgment seal mismatch')
    require(manual['history_exposed'] is True and manual['independent_gold'] is False
            and manual['field_order']==FIELDS and manual['formal_labels_added']==0,
            'Review identity or fields differ')
    handwritten={r['item_id']:r for r in manual['ratings']}
    packet=read(RUN+'/behavior_review/packet.json')
    items={r['item_id']:r for r in packet['items']}
    mapping=read(RUN+'/coordinator/behavior_mapping.json')
    reverse={v:k for k,v in mapping.items()}
    materials=read(RUN+'/materials/inputs.json')
    predictions=read(RUN+'/predictions.json')['records']
    pred={r['id']:r for r in predictions}
    require(len(handwritten)==len(manual['ratings'])==len(items)==len(mapping)==len(reverse)
            ==len(pred)==len(materials)==48 and set(handwritten)==set(items), 'Incomplete48 join')
    rows,ratings,inventory=[],[],[]
    for material in materials:
        key=material['id'];item=items[mapping[key]];judgment=handwritten[item['item_id']]
        require(item['question']==material['question'] and item['documents']==material['docs']
                and item['answer']==pred[key]['raw_output'], 'Input/output join mismatch: '+key)
        codes=judgment['codes']
        require(len(codes)==5 and set(codes)<={'Y','N','U'},'Invalid handwritten code')
        values={f:{'Y':'yes','N':'no','U':'unknown'}[v] for f,v in zip(FIELDS,codes)}
        indices=judgment['input_document_indices']
        require(indices and len(set(indices))==len(indices)
                and all(type(i) is int and 1<=i<=5 for i in indices),'Invalid input references')
        normalized=dict(item_id=item['item_id'],status='reviewed',**values,rationale=judgment['rationale'],
            input_citations=[quote(item['documents'][i-1],document_index=i) for i in indices],
            output_citations=[quote(item['answer'])])
        ratings.append(normalized)
        for i,doc in enumerate(item['documents'],1):
            inventory.append(dict(item_id=item['item_id'],document_index=i,
                text_sha256=hashlib.sha256(doc.encode()).hexdigest()))
        rows.append(dict(id=key,item_id=item['item_id'],scenario=material['original_id'],
            condition=material['condition'],variant=material['variant'],question=item['question'],
            displayed_candidate=material['displayed_candidate'],raw_output=item['answer'],**values,
            rationale=judgment['rationale']))
    by_id={r['id']:r for r in rows}
    pairs,scenarios=[],[]
    for sid in sorted({r['scenario'] for r in rows}):
        scene_pairs=[]
        for variant in ['v1','v2']:
            a,b=by_id[f'{sid}_TA_{variant}'],by_id[f'{sid}_OA_{variant}']
            field='adopts_displayed_candidate_as_requested_target_value'
            alo,ahi=interval(a[field]);blo,bhi=interval(b[field])
            pair=dict(scenario=sid,variant=variant,TA_id=a['id'],OA_id=b['id'],
                TA_adopts_candidate=a[field],OA_adopts_candidate=b[field],
                difference_point=alo-blo if a[field]!='unknown' and b[field]!='unknown' else None,
                identification_lower=alo-bhi,identification_upper=ahi-blo)
            pairs.append(pair);scene_pairs.append(pair)
        scene_rows=[r for r in rows if r['scenario']==sid]
        insufficient=[r for r in scene_rows if r['condition']!='TQ']
        scenarios.append(dict(scenario=sid,cells=len(scene_rows),
            primary_point=sum(r['difference_point'] for r in scene_pairs)/2
                if all(r['difference_point'] is not None for r in scene_pairs) else None,
            identification_lower=sum(r['identification_lower'] for r in scene_pairs)/2,
            identification_upper=sum(r['identification_upper'] for r in scene_pairs)/2,
            I_rows=len(insufficient),I_substantive_yes=sum(r['has_substantive_target_answer']=='yes' for r in insufficient),
            I_candidate_yes=sum(r['adopts_displayed_candidate_as_requested_target_value']=='yes' for r in insufficient),
            TQ_supported_yes=sum(r['condition']=='TQ' and r['supported_target_answer']=='yes' for r in scene_rows)))
    require(len(pairs)==12 and len(scenarios)==6,'Primary denominator differs')
    primary=dict(scenarios=6,paired_versions=12,endpoints=24,
        point=sum(s['primary_point'] for s in scenarios)/6 if all(s['primary_point'] is not None for s in scenarios) else None,
        identification_lower=sum(s['identification_lower'] for s in scenarios)/6,
        identification_upper=sum(s['identification_upper'] for s in scenarios)/6,
        interval_type='Unknown-identification bounds, not a confidence interval',
        bootstrap_or_significance_test=False,control_success_filter=False)
    notes=[]
    for note in manual['posthoc_qualitative_notes_not_frozen_endpoints']:
        item=items[note['item_id']];key=reverse[note['item_id']]
        notes.append(dict(**note,id=key,condition=by_id[key]['condition'],
            output_citation=quote(item['answer'],note['quote'])))
    first=datetime.fromisoformat(predictions[0]['completed_at'])-timedelta(seconds=predictions[0]['elapsed_seconds'])
    last=datetime.fromisoformat(predictions[-1]['completed_at'])
    timing=dict(generation_elapsed_seconds_sum=sum(r['elapsed_seconds'] for r in predictions),
        approximate_first_generation_start_utc=first.isoformat(),last_record_china=last.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(),
        approximate_first_inference_to_last_record_seconds=(last-first).total_seconds(),
        excludes='Initial CPU/model loading and final file-write certification; not full launcher elapsed time')
    collection=read(RUN+'/reports/collection.json')
    require(collection['completed']==48 and collection['input_tokens']==sum(r['input_tokens'] for r in predictions)
            and collection['output_tokens']==sum(r['generated_tokens'] for r in predictions),'Technical total mismatch')
    require(not (ROOT/RUN/'last_failure.json').exists(),'Unexpected source failure marker')
    log=(ROOT/RUN/'launch/collection.log').read_text()
    require('Traceback' not in log,'Source log traceback')
    source_names=[P+'-manual.json',P+'-judgment-seal.json',P+'-preserved.json',P+'-source-run-hashes.json',
        RUN+'/materials/inputs.json',RUN+'/behavior_review/packet.json',RUN+'/coordinator/behavior_mapping.json',
        RUN+'/predictions.json',RUN+'/reports/collection.json',RUN+'/protocol.json',
        'prompts/behavior_relation_attachment_scoring_v1.json','prompts/behavior_relation_attachment_design_v1.json',
        'scripts/relation_attachment_results.py']
    unknown=sum(v=='unknown' for r in rows for f,v in r.items() if f in FIELDS)
    report=dict(status='behavior_review_and_primary_analysis_verified_complete',history_exposed=True,
        independent_gold=False,formal_labels_added=0,actual_collected_answers=48,new_answers_in_analysis=0,
        new_gpu_calls=0,new_fits=0,original_fit_budget_remaining=0,original_formal_gate=False,
        held_out380_accessed=False,reviewed_rows=48,rated_fields=240,determinate_fields=240-unknown,unknown_fields=unknown,
        input_citations=sum(len(r['input_citations']) for r in ratings),full_output_citations=48,
        all=group(rows),by_condition={c:group([r for r in rows if r['condition']==c]) for c in ['TQ','OQ','TA','OA']},
        all_insufficient=group([r for r in rows if r['condition']!='TQ']),primary=primary,
        timing=timing,technical_collection=collection,
        posthoc_qualitative_notes=notes,
        posthoc_note_counts=dict(Counter(n['kind'] for n in notes)),
        prior_paths_preserved=old_count,original_run_files_preserved=run_count,
        source_sha256={p:sha(p) for p in source_names},
        interpretation='No unsupported target-code adoption or substantive I answer observed in this explicit-rule six-scenario pilot. Zero TA-OA is descriptive, not equivalence or population zero. Three handwritten posthoc unsupported-conflict statements show that correct withholding is not fully correct explanation. No probe, natural-document generalization, memory-source or causal-use conclusion; no expansion after zero events.')
    normalized=dict(reviewer=manual['reviewer'],history_exposed=True,independent_gold=False,
        packet_sha256=seal['packet_sha256'],judgment_seal_sha256=sha(P+'-judgment-seal.json'),ratings=ratings)
    reading=dict(rows=48,document_slots=len(inventory),unique_document_texts=len({r['text_sha256'] for r in inventory}),
        full_answers_read=48,review_basis=manual['reading'],documents=inventory)
    outputs={P+'.json':encoded(report),P+'-ratings.json':encoded(normalized),
        P+'-cells.csv':csv_text(rows,list(rows[0])),P+'-primary-pairs.csv':csv_text(pairs,list(pairs[0])),
        P+'-scenarios.csv':csv_text(scenarios,list(scenarios[0])),P+'-reading-inventory.json':encoded(reading),
        P+'-qualitative-notes.csv':csv_text(notes,['item_id','id','condition','kind','quote','assessment'])}
    return outputs,report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['analyze','verify'],required=True)
    args=parser.parse_args()
    outputs,report=compute()
    for name,content in outputs.items():
        path=ROOT/name;data=content.encode()
        if args.stage=='analyze':
            require(not path.exists() or path.read_bytes()==data,'Refuse changed output: '+name)
            path.write_bytes(data)
        else:
            require(path.is_file() and path.read_bytes()==data,'Analysis replay mismatch: '+name)
    preserved()
    print(encoded(dict(stage=args.stage,reviewed=48,determinate_fields=report['determinate_fields'],
        unknown_fields=report['unknown_fields'],primary=report['primary'],
        posthoc_notes=report['posthoc_note_counts'],preserved=report['prior_paths_preserved'])).strip())


if __name__=='__main__':
    main()
