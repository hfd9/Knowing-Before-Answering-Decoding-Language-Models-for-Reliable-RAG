"""CPU-only assembly and audit of the frozen cross-expression semantic material budget."""

import argparse
from collections import Counter, defaultdict
import difflib
import hashlib
import html
import itertools
import json
from pathlib import Path
import random
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/'prompts/semantic_transfer_validation_v1.json'
AUTHORED=ROOT/'prompts/semantic_transfer_materials_v1.json'
DEFAULT=ROOT/'runs/qwen2.5-3b-semantic-transfer-materials-v1'
ARCHIVE=ROOT/'dataset/instances.zip'
MANIFEST=ROOT/'runs/qwen2.5-3b-small/data/manifest.json'
TRAIN600=ROOT/'runs/qwen2.5-3b-small/data/instances_train.jsonl'
OLD_FREE=ROOT/'runs/qwen2.5-3b-free-answer-study/protocol.json'
OLD_PROBE=ROOT/'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'
CONDITIONS=['S','K','I','C']
PROPOSED=dict(S='answer',K='answer',I='refuse',C='conflict')


def read(path):return json.loads(Path(path).read_text())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def text_hash(text):return hashlib.sha256(text.encode()).hexdigest()
def json_text(value):return json.dumps(value,ensure_ascii=False,indent=2)+'\n'


def put(path,value,write):
    put_text(path,json_text(value),write)


def put_text(path,expected,write):
    if path.exists():
        if path.read_text()!=expected:raise ValueError(f'Existing material differs: {path}')
    elif write:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(expected)
    else:raise ValueError(f'Missing material: {path}')


def load_sources():
    design=read(DESIGN);spec=read(AUTHORED);manifest=read(MANIFEST)
    assert digest(ARCHIVE)==design['source']['archive_sha256']
    assert digest(MANIFEST)==design['source']['sampled_train_manifest_sha256']
    with zipfile.ZipFile(ARCHIVE) as archive:
        # Never open any validation or test archive member.
        rows=[json.loads(line) for line in archive.read('instances_train.jsonl').decode().splitlines() if line.strip()]
    assert len(rows)==5463 and all(r['split']=='train' for r in rows)
    excluded=set(manifest['splits']['train']['original_ids'])
    eligible={r['original_id'] for r in rows}-excluded
    salt=design['source']['salt']
    chosen=sorted(eligible,key=lambda oid:text_hash(salt+'|'+oid))[:30]
    partition={oid:part for part,ids in design['partitions'].items() for oid in ids}
    assert chosen==list(partition) and len(partition)==30
    assert [len(x) for x in design['partitions'].values()]==[12,6,12]
    lookup={r['id']:r for r in rows}
    selected={oid:{mode:lookup[oid+'_'+mode] for mode in ['answer','refuse']} for oid in chosen}
    assert all(oid not in excluded for oid in selected)
    old_questions={' '.join(r['question'].lower().split()) for r in rows if r['original_id'] in excluded}
    assert not {' '.join(v['answer']['question'].lower().split()) for v in selected.values()} & old_questions
    assert len({v['answer']['question'] for v in selected.values()})==30
    return design,spec,selected,partition


def build_catalog(selected):
    documents={};bases=[];source_answer=[]
    for oid,group in selected.items():
        answer,refuse=group['answer'],group['refuse'];source_answer.append(answer)
        slots=sorted(sorted(range(5),key=lambda i:(len(refuse['docs'][i]),i))[:3])
        bg=[refuse['docs'][i] for i in slots]
        entry=dict(original_id=oid,question=answer['question'],gold_answer=answer['gold_answer'],
                   source_doc_ids=[],background_doc_ids=[],background_source_slots=[i+1 for i in slots])
        for field,texts in [('source_doc_ids',answer['docs']),('background_doc_ids',bg)]:
            for text in texts:
                hashed=text_hash(text)
                if hashed not in documents:documents[hashed]=dict(doc_id=f'T{len(documents)+1:03d}',sha256=hashed,text=text,uses=[])
                documents[hashed]['uses'].append(oid+':'+field)
                entry[field].append(documents[hashed]['doc_id'])
        bases.append(entry)
    return dict(documents=list(documents.values()),bases=bases),source_answer


def offsets(old,new,slot):
    return [dict(doc_slot=slot,before_start=i,before_end=j,after_start=k,after_end=l,before=old[i:j],after=new[k:l])
            for tag,i,j,k,l in difflib.SequenceMatcher(a=old,b=new,autojunk=False).get_opcodes() if tag!='equal']


def assemble(design,spec,selected,partition,catalog):
    order=list(partition);units={u['original_id']:u for u in spec['units']}
    assert list(units)==order and len(units)==30 and spec['independent_gold'] is False
    source_docs={d['doc_id']:d for d in catalog['documents']}
    bases={b['original_id']:b for b in catalog['bases']}
    assert spec['source_reading']['all_ids_read']==list(source_docs)
    assert len(source_docs)==spec['source_reading']['unique_full_passages']==154
    inputs=[];missing=[];judgments=[];edits=[];reviews=[]
    slot_pairs=list(itertools.combinations(range(5),2))
    for number,oid in enumerate(order,1):
        unit=units[oid];source=bases[oid];slots=slot_pairs[(number-1)%10]
        assert unit['independent_gold'] is False and unit['reviewer']=='current_coordinator_author_background_exposed'
        for c in unit['source_citations']:
            document=source_docs[c['doc_id']]
            assert document['sha256']==c['source_sha256']
            assert document['text'][c['start']:c['end']]==c['quote']
        complete=unit['status']=='authored_pending_independent_review'
        assert (unit['expressions'] is not None)==complete
        reviews.append(dict(original_id=oid,partition=partition[oid],status=unit['status'],source_question=selected[oid]['answer']['question'],
            material_question=unit['question'],question_change_reason=unit['question_change_reason'],source_citations=unit['source_citations'],
            source_background_slots=source['background_source_slots'],background_doc_ids=source['background_doc_ids'],
            target_slots=[i+1 for i in slots],independent_gold=False,
            blocker_category=unit.get('blocker_category'),blocker_reason=unit.get('blocker_reason')))
        for expression in ['A','B']:
            for condition in CONDITIONS:
                key=f'stv{number:02d}_{expression}_{condition}'
                if not complete:
                    missing.append(dict(id=key,original_id=oid,partition=partition[oid],expression=expression,condition=condition,
                        status='incomplete_source_or_scope',semantic_label=None,reason=unit['blocker_reason']))
                    continue
                assert set(unit['expressions'])=={'A','B'} and set(unit['expressions'][expression])==set(CONDITIONS)
                targets=unit['expressions'][expression][condition]
                assert len(targets)==2 and all(isinstance(t,str) and t.strip() for t in targets)
                background=iter([source_docs[k]['text'] for k in source['background_doc_ids']])
                docs=[targets[slots.index(i)] if i in slots else next(background) for i in range(5)]
                row=dict(id=key,original_id=oid,partition=partition[oid],expression=expression,condition=condition,
                    question=unit['question'],docs=docs,target_slots=[i+1 for i in slots],semantic_label=None)
                inputs.append(row)
                cites=[dict(doc_slot=slot+1,start=0,end=len(text),quote=text,role='authored_target',source_text_sha256=text_hash(text)) for slot,text in zip(slots,targets)]
                mode=PROPOSED[condition]
                detail={'S':'Target claims together support the stated answer under the fixed question scope.',
                        'K':unit['compatibility_explanation'],'I':unit['missing_premise'],'C':unit['conflict_explanation']}[condition]
                judgments.append(dict(id=key,original_id=oid,partition=partition[oid],author_proposed_mode=mode,semantic_label=None,
                    required_facts=unit['required_facts'],support_chain=[detail],
                    author_answer_if_supported=unit['authored_answer'] if condition in ['S','K'] else None,
                    missing_premise=unit['missing_premise'] if condition=='I' else None,
                    conflicting_claims=unit['conflict_explanation'] if condition=='C' else None,
                    compatibility=unit['compatibility_explanation'] if condition=='K' else None,
                    citations=cites,independent_gold=False,review_status='author_proposal_pending_two_history_blind_reviews'))
                if condition!='S':
                    baseline=unit['expressions'][expression]['S']
                    differences=[]
                    for slot,old,new in zip(slots,baseline,targets):differences.extend(offsets(old,new,slot+1))
                    assert differences
                    if condition=='C':assert targets[0]==baseline[0] and all(d['doc_slot']==slots[1]+1 for d in differences)
                    edits.append(dict(id=key,reference=f'stv{number:02d}_{expression}_S',changes=differences))
    assert len(inputs)+len(missing)==240 and len(inputs)==len(judgments)
    by_base=Counter(r['original_id'] for r in inputs)
    assert all(n==8 for n in by_base.values()) and len({r['id'] for r in inputs+missing})==240
    lookup={r['id']:r for r in inputs};pairs=[]
    for oid in by_base:
        own=[r for r in inputs if r['original_id']==oid]
        for condition in CONDITIONS:
            a=next(r for r in own if r['expression']=='A' and r['condition']==condition)
            b=next(r for r in own if r['expression']=='B' and r['condition']==condition)
            pairs.append(dict(original_id=oid,partition=partition[oid],kind='expression_'+condition,left_id=b['id'],right_id=a['id']))
        for expression in ['A','B']:
            a=next(r for r in own if r['expression']==expression and r['condition']=='S')
            for condition in ['K','I','C']:
                b=next(r for r in own if r['expression']==expression and r['condition']==condition)
                assert b['question']==a['question'] and b['target_slots']==a['target_slots']
                non_targets=[i for i in range(5) if i+1 not in a['target_slots']]
                assert all(a['docs'][i]==b['docs'][i] for i in non_targets)
                pairs.append(dict(original_id=oid,partition=partition[oid],kind=expression+'_'+condition+'_minus_S',left_id=b['id'],right_id=a['id']))
        assert len({r['partition'] for r in own})==1 and len({r['question'] for r in own})==1
    assert len(pairs)==len(by_base)*10
    for pair in pairs:assert lookup[pair['left_id']]['partition']==lookup[pair['right_id']]['partition']
    return inputs,missing,judgments,edits,reviews,pairs


def make_review_packets(inputs):
    packets={};mapping={}
    for reviewer,seed in [('a',2026102031),('b',2026102032)]:
        order=list(inputs);random.Random(seed).shuffle(order);items=[]
        for index,row in enumerate(order,1):
            ticket=f'R{index:03d}'
            items.append(dict(item_id=ticket,question=row['question'],documents=row['docs']))
            mapping.setdefault(row['id'],{})[reviewer]=ticket
        assert all(set(r)=={'item_id','question','documents'} for r in items)
        packets[reviewer]=dict(task='input_evidence_semantics_review',items=items)
    return packets,mapping


def overlap_audit(inputs,catalog,partition):
    documents={d['doc_id']:d for d in catalog['documents']};bases={r['original_id']:r for r in catalog['bases']}
    used=defaultdict(set)
    for oid in {r['original_id'] for r in inputs}:
        for doc in bases[oid]['background_doc_ids']:used[doc].add(partition[oid])
    crossing=[dict(doc_id=doc,sha256=documents[doc]['sha256'],partitions=sorted(parts)) for doc,parts in used.items() if len(parts)>1]
    old=[json.loads(line) for line in TRAIN600.read_text().splitlines() if line.strip()]
    assert len(old)==600 and all(r['split']=='train' for r in old)
    old_hashes={text_hash(t) for r in old for t in r['docs']}
    return dict(shared_backgrounds_across_partitions=crossing,unique_used_backgrounds=len(used),
        used_backgrounds_exactly_seen_in_old_probe_train=sum(documents[doc]['sha256'] in old_hashes for doc in used),
        caveat='Base IDs and exact questions are held out from old probe training, not all entity knowledge or background documents. Shared background bytes are disclosed, not proof of OOD or target-fact leakage. No reassignment or background cleaning based on outputs.')


def prepare(base,write=True):
    design,spec,selected,partition=load_sources();catalog,source_answer=build_catalog(selected)
    inputs,missing,judgments,edits,reviews,pairs=assemble(design,spec,selected,partition,catalog)
    import evidence_experiment as e
    from transformers import AutoTokenizer
    model=read(OLD_FREE)['model'];tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
    config=read(Path(model)/'config.json');context=config['max_position_embeddings']
    lengths={};prompts={}
    for row in inputs:
        prompt=e.render_input(row,'free_answer','chat',tokenizer)
        count=len(e.encode(tokenizer,prompt,'chat')['input_ids']);assert count+128<=context
        lengths[row['id']]=count;prompts[row['id']]=text_hash(prompt)
    for pair in pairs:pair['input_token_delta']=lengths[pair['left_id']]-lengths[pair['right_id']]
    packets,mapping=make_review_packets(inputs)
    rubric=dict(task='Read the question and all five full supplied documents; judge evidence without external factual knowledge.',
        independence='Do not receive repository AGENTS.md/history, author labels, other review results or probe/model outputs. Disclose any exposure; background-exposed checks cannot satisfy the gate.',
        modes=dict(answer='Complete supported answer with no relevant incompatible claim; different aliases, scope granularity, ranks, time or properties can coexist.',
                   refuse='A necessary premise or entity/event/time link is missing; no genuine relevant incompatibility is established.',
                   conflict='Same target/event/time/requested property has mutually exclusive claims without evidence-based resolution.',unknown='Unresolved ambiguity: explain alternatives.'),
        rules=['Assess all required entities/relations. Do not turn a name into a missing relationship.',
               'Supplied counterfactual assertions are evidence; do not repair them using world knowledge.',
               'Check explicit negative claims, natural single-valued totals/ranks, compatible co-contributors and real source-priority/time corrections.',
               'Write a support chain, exact document quotes, missing facts or incompatible claims and possible resolution.',
               'Do not infer labels from repeated wording or related items. Preserve ambiguity.'],
        output_schema=dict(reviewer='',history_exposed=None,exposure_description='',packet_sha256='',
            ratings=[dict(item_id='',semantic_mode='answer/refuse/conflict/unknown',confidence='high/moderate/ambiguous',
                required_facts=[],support_chain=[],missing_facts=[],conflicting_claims=[],resolution_basis='',rationale='',citations=[dict(doc_slot=1,quote='')])]))
    split_counts={part:dict(planned_bases=len(ids),constructed_bases=len({r['original_id'] for r in inputs if r['partition']==part}),
        planned_cells=8*len(ids),constructed_cells=sum(r['partition']==part for r in inputs),
        unavailable_cells=sum(r['partition']==part for r in missing)) for part,ids in design['partitions'].items()}
    coverage=len(inputs)/240
    preflight=dict(status='cpu_material_preflight_passed_not_semantic_approval',planned_cells=240,constructed_cells=len(inputs),unavailable_cells=len(missing),
        construction_coverage=coverage,partitions=split_counts,input_tokens=lengths,min_input_tokens=min(lengths.values()),max_input_tokens=max(lengths.values()),
        total_input_tokens=sum(lengths.values()),context_tokens=context,answer_budget=128,max_output_tokens_total=128*len(inputs),
        prompt_sha256=prompts,independently_labeled_cells=0,semantic_coverage=0.0,
        coverage_note='Construction coverage is not semantic-label coverage. Planned denominator240 retained; incomplete bases not replaced. At this construction coverage, the frozen90% semantic coverage pass requirement cannot be reached.',
        no_model_weights_loaded=True,no_probe_deserialized=True,new_gpu_forwards=0,generated_answers=0,trained_probes=0,
        candidate_layers=[28],max_new_training_fits=1)
    assert digest(OLD_PROBE)==design['probe']['old_source_pkl_sha256']
    protocol=dict(schema_version=1,task='semantic_transfer_material_preparation_only',
        design_sha256=digest(DESIGN),authored_sha256=digest(AUTHORED),source_archive_sha256=digest(ARCHIVE),
        model=model,tokenizer_sha256={name:digest(Path(model)/name) for name in ['config.json','tokenizer.json','tokenizer_config.json']},
        free_instruction_sha256=text_hash(e.FREE_INSTRUCTION),feature_convention=e.FEATURE_CONVENTION,
        implementation_sha256={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'scripts/run_semantic_transfer_materials.sh',ROOT/'scripts/evidence_experiment.py',ROOT/'code/prompts.py',ROOT/'prompts/baseline_prompts.json']},
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in [MANIFEST,TRAIN600,OLD_FREE,OLD_PROBE]},
        packet_sha256={k:text_hash(json_text(v)) for k,v in packets.items()},inputs_sha256=text_hash(json_text(inputs)),
        no_gold='Author intents only; all semantic labels null until auditable independent reviews. Existing background-exposed40 not imported.',
        no_gpu='CPU prepare/verify only. No inference, generation, fitting, calibration or confirmation access.')
    gate=dict(status='blocked_pending_history_blind_semantic_reviews_and_coverage',gpu_launch_ready=False,
        independent_reviews_completed=0,independently_labeled_cells=0,constructed_cells=len(inputs),planned_cells=240,
        construction_coverage=coverage,minimum_frozen_semantic_coverage=0.90,
        reasons=['No two history-independent input reviews available.','Incomplete source/scope cells cannot be auto-labeled or silently excluded; construction coverage is below90%.'],
        author_intents_must_not_be_used_as_training_gold=True,do_not_run_gpu=True)
    artifacts={'source_catalog.json':catalog,'source_train_answer30.json':source_answer,'materials/inputs.json':inputs,
        'materials/unavailable_cells.json':missing,'coordinator/author_judgments.json':judgments,'coordinator/base_audit.json':reviews,
        'coordinator/edit_provenance.json':edits,'coordinator/pairs.json':pairs,'coordinator/review_mapping.json':mapping,
        'reports/overlap_audit.json':overlap_audit(inputs,catalog,partition),'preflight.json':preflight,'protocol.json':protocol,'review_gate.json':gate,
        'progress.json':dict(status='materials_prepared_review_pending_no_gpu',planned=240,constructed=len(inputs),unavailable=len(missing),saved_gpu=0)}
    for reviewer,packet in packets.items():
        artifacts['review_'+reviewer+'/packet.json']=packet
        artifacts['review_'+reviewer+'/rubric.json']=rubric
        artifacts['review_'+reviewer+'/ratings_template.json']=dict(reviewer='',history_exposed=None,exposure_description='',packet_sha256=protocol['packet_sha256'][reviewer],
            ratings=[dict(item_id=x['item_id'],semantic_mode='unknown',status='unreviewed',rationale='') for x in packet['items']])
    for name,value in artifacts.items():put(base/name,value,write)
    body=['<!doctype html><meta charset="utf-8"><title>Semantic transfer author review</title><style>body{max-width:1100px;margin:auto;font:16px sans-serif}pre{white-space:pre-wrap}article{padding:1em;border-bottom:2px solid #aaa}</style><h1>Author proposals: not independently approved</h1>']
    for row,j in zip(inputs,judgments):
        body.append('<article><h2>'+html.escape(row['id']+' / '+row['original_id']+' / '+row['partition'])+'</h2><p>'+html.escape(row['question'])+'</p><p>AUTHOR PROPOSAL: '+j['author_proposed_mode']+'; semantic_label=null</p>'+''.join('<details><summary>Document '+str(i)+'</summary><pre>'+html.escape(text)+'</pre></details>' for i,text in enumerate(row['docs'],1))+'<p>'+html.escape(j['support_chain'][0])+'</p></article>')
    body.append('<h2>Unavailable planned cells</h2><pre>'+html.escape(json_text(missing))+'</pre>')
    put_text(base/'coordinator/author_review.html',''.join(body),write)
    for reviewer,packet in packets.items():
        page='<!doctype html><meta charset="utf-8"><title>Evidence review</title><style>body{max-width:1000px;margin:auto}pre{white-space:pre-wrap}</style><h1>Input evidence review</h1><pre>'+html.escape(json_text(rubric))+'</pre>'+''.join('<article><h2>'+r['item_id']+'</h2><p>'+html.escape(r['question'])+'</p>'+''.join('<h3>Document '+str(i)+'</h3><pre>'+html.escape(t)+'</pre>' for i,t in enumerate(r['documents'],1))+'</article>' for r in packet['items'])
        put_text(base/('review_'+reviewer+'/review.html'),page,write)
    return dict(status='prepared_verified_no_gpu' if write else 'verified_read_only_no_gpu',constructed=len(inputs),unavailable=len(missing),planned=240,
        constructed_bases=len(inputs)//8,independent_semantic_labels=0,review_gate_ready=False,min_tokens=preflight['min_input_tokens'],max_tokens=preflight['max_input_tokens'],
        total_tokens=preflight['total_input_tokens'],partitions=split_counts,source_unique_full_documents=len(catalog['documents']),source_citations=sum(len(u['source_citations']) for u in spec['units']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','verify'],default='prepare')
    parser.add_argument('--run_dir',type=Path,default=DEFAULT)
    args=parser.parse_args();base=args.run_dir.resolve()
    assert base.is_relative_to(ROOT/'runs') and base.name.startswith('qwen2.5-3b-semantic-transfer-materials-')
    if args.stage=='prepare':base.mkdir(parents=True,exist_ok=True)
    print(json_text(prepare(base,write=args.stage=='prepare')))


if __name__=='__main__':main()
