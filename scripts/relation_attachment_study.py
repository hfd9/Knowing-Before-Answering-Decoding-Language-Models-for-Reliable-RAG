"""Fixed48 behavior pilot: new materials, CPU preflight and strict single-attempt collection.

Reuse the frozen binding study's renderer/model fingerprint/one-answer generator.
Do not modify its files or run, load probes, collect hidden states, fit or resample.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import html
from itertools import permutations, product
import json
import math
from pathlib import Path
import re

import behavior_binding_study as core

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT/'runs/qwen2.5-3b-relation-attachment-v1'
SPEC = ROOT/'prompts/behavior_relation_attachment_materials_v1.json'
DESIGN = ROOT/'prompts/behavior_relation_attachment_design_v1.json'
RUBRIC = ROOT/'prompts/behavior_relation_attachment_scoring_v1.json'
REVIEW = ROOT/'prompts/behavior_relation_attachment_author_review_v1.json'
EXAMPLES = ROOT/'docs/records/2026-10-23-behavior-structure-audit-samples.json'
BUDGET = ROOT/'runs/semantic-transfer-shared-one-fit-budget-v1.json'
FIT_SEAL = ROOT/'docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json'
OLD_LABELS = ROOT/'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/approved_labels.json'
FIELDS = ['has_substantive_target_answer', 'adopts_displayed_candidate_as_requested_target_value',
          'supported_target_answer', 'acknowledges_missing_target_attribute', 'claimed_evidence_supports_target']
read, encoded, sha, digest, save, require = core.read, core.encoded, core.sha, core.digest, core.save, core.require
runtime, generate, smoke_gate, renderer_inputs = core.runtime, core.generate, core.smoke_gate, core.renderer_inputs
FACT = re.compile(r'The (access code|inspection code) assigned to Unit (U-\d{3}) is (K-\d{5})\. Unit (U-\d{3}) has a ledger entry\.')


def original_state():
    seal, budget = read(FIT_SEAL), read(BUDGET)
    require(seal['fit_attempts']==1 and seal['remaining_original_design_fits']==0
            and budget['maximum_attempts']==1, 'Original fit state differs')
    require(all(digest(ROOT/p)==h for p,h in seal['files'].items()), 'Fit-sealed source changed')
    require(len(read(OLD_LABELS))==240 and all(v is None for v in read(OLD_LABELS).values()),
            'Original formal labels changed')


def make_materials(spec=None):
    spec = read(SPEC) if spec is None else spec
    draft = read(DESIGN)
    require(spec['base_scenarios']==6 and spec['maximum_generations']==48
            and spec['max_new_tokens']==128 and spec['new_probe_fits']==0
            and spec['collection_allowed'] is True and spec['independent_semantic_approval'] is False
            and spec['review_fields']==FIELDS and spec['cells']==list(draft['cells']), 'Scope changed')
    for key in ['question_template','candidate_document_template','background_templates_in_order']:
        require(spec[key]==draft[key], 'Draft language changed: '+key)
    rows, worlds = [], {}
    for s in spec['scenarios']:
        for cell, variant in product(spec['cells'], ('v1','v2')):
            roles = draft['cells'][cell]
            owner = s['target'] if roles['owner']=='target' else s['other']
            nonowner = s['other'] if owner==s['target'] else s['target']
            attr = s['queried_attribute'] if roles['attribute']=='queried' else s['alternative_attribute']
            value = s[variant]
            docs = [d.format(**s) for d in spec['background_templates_in_order']]
            docs.insert(s['candidate_slot']-1, spec['candidate_document_template'].format(
                attribute=attr, owner=owner, nonowner=nonowner, candidate=value))
            row = dict(id=f"{s['id']}_{cell}_{variant}", original_id=s['id'],condition=cell,
                variant=variant, question=spec['question_template'].format(**s),docs=docs,
                target_entity=s['target'], other_entity=s['other'],queried_attribute=s['queried_attribute'],
                displayed_candidate=value,candidate_slot=s['candidate_slot'],fictional=True)
            rows.append(row)
            if cell!='TQ':
                completions=[]
                for target_value in (value,s['witness_alternative']):
                    assignment={pair:s['witness_alternative'] for pair in product(
                        (s['target'],s['other']),('access code','inspection code'))}
                    assignment[(owner,attr)]=value
                    assignment[(s['target'],s['queried_attribute'])]=target_value
                    completions.append([dict(entity=e,attribute=a,value=v) for (e,a),v in sorted(assignment.items())])
                worlds[row['id']]=dict(input_sha256=sha(encoded(renderer_inputs(row)).decode()),
                    worlds=completions,role='Compatible completions, not hidden correct answers; never render')
    validate_materials(rows,worlds,spec)
    return rows,worlds


def validate_materials(rows,worlds,spec):
    require(len(rows)==len({r['id'] for r in rows})==48 and len(spec['scenarios'])==6,
            'Wrong full48 grid')
    scenarios={s['id']:s for s in spec['scenarios']}
    require(len(scenarios)==6 and len({s[k] for s in scenarios.values() for k in ['target','other']})==12,
            'Repeated scenario/entity')
    require(len({s[k] for s in scenarios.values() for k in ['v1','v2','witness_alternative']})==18,
            'Code collision')
    require([s['candidate_slot'] for s in spec['scenarios']]==[1,4,2,5,3,1], 'Candidate slots changed')
    require(Counter(s['queried_attribute'] for s in scenarios.values())=={'access code':3,'inspection code':3},
            'Query directions differ')
    ranks=[]
    for s in scenarios.values():
        require({s['queried_attribute'],s['alternative_attribute']}=={'access code','inspection code'}, 'Fields overlap')
        codes=[s[k] for k in ['v1','v2','witness_alternative']]
        ranks.append(tuple(sorted(codes).index(c) for c in codes))
    require(Counter(ranks)==Counter(permutations(range(3))), 'Code-rank permutations not balanced')
    require(sum(s['target']<s['other'] for s in scenarios.values())==3, 'Entity rank unbalanced')
    expected={f'{sid}_{c}_{v}' for sid,c,v in product(scenarios,spec['cells'],('v1','v2'))}
    require({r['id'] for r in rows}==expected, 'Incomplete cell/variant grid')
    require(len(set(spec['smoke_prefix_ids']))==4 and set(spec['smoke_prefix_ids'])<=expected,
            'Invalid fixed smoke prefix')
    require(Counter(k.split('_')[1] for k in spec['smoke_prefix_ids'])==Counter(spec['cells']),
            'Smoke must cover all four cells')
    by_id={r['id']:r for r in rows}
    insufficient=set()
    for row in rows:
        s=scenarios[row['original_id']]
        require(row['question']==spec['question_template'].format(**s), 'Question drift/leak')
        require(len(row['docs'])==5, 'Wrong document slots')
        idx=s['candidate_slot']-1
        fact=FACT.fullmatch(row['docs'][idx])
        require(fact is not None, 'Invalid candidate document')
        attr,owner,value,nonowner=fact.groups()
        require({owner,nonowner}=={s['target'],s['other']} and owner!=nonowner, 'Entity mismatch')
        require(value==s[row['variant']]==row['displayed_candidate'], 'Variant/value mismatch')
        roles=read(DESIGN)['cells'][row['condition']]
        require(owner==(s['target'] if roles['owner']=='target' else s['other'])
                and attr==(s['queried_attribute'] if roles['attribute']=='queried' else s['alternative_attribute']),
                'Displayed argument/condition mismatch')
        require([d for i,d in enumerate(row['docs']) if i!=idx]==[
            d.format(**s) for d in spec['background_templates_in_order']], 'Background changed')
        text=row['question']+'\n'+'\n'.join(row['docs'])
        require(re.findall(r'K-\d{5}',text)==[value], 'Witness/unused-code leakage')
        sufficient=owner==s['target'] and attr==s['queried_attribute']
        require(sufficient==(row['condition']=='TQ'), 'Support relation mismatch')
        if not sufficient:
            insufficient.add(row['id'])
            require(row['id'] in worlds, 'Missing I witness')
            witness=worlds[row['id']]
            require(witness['input_sha256']==sha(encoded(renderer_inputs(row)).decode()), 'Witness packet mismatch')
            require(len(witness['worlds'])==2, 'Need two worlds')
            actual=[]
            domain=set(product((s['target'],s['other']),('access code','inspection code')))
            for world in witness['worlds']:
                assignment={(a['entity'],a['attribute']):a['value'] for a in world}
                require(len(world)==len(assignment)==4 and set(assignment)==domain,
                        'World must be a complete four-pair function')
                require(assignment[(owner,attr)]==value and all(re.fullmatch(r'K-\d{5}',v)
                    for v in assignment.values()), 'World contradicts displayed fact')
                actual.append(assignment)
            a,b=actual
            require({key for key in a if a[key]!=b[key]}=={(s['target'],s['queried_attribute'])},
                    'Worlds differ beyond missing query')
            require({a[(s['target'],s['queried_attribute'])],b[(s['target'],s['queried_attribute'])]}
                    =={value,s['witness_alternative']}, 'Wrong target completions')
        else:
            require(row['id'] not in worlds,'Sufficient row has I worlds')
    require(set(worlds)==insufficient and len(worlds)==36,'Orphan/missing worlds')
    # Preserve all16 examples exactly; no output/tokenizer-based revisions.
    for old in read(EXAMPLES)['items']:
        row=by_id[old['id']]
        require(old['question']==row['question'] and old['documents']==row['docs'], 'Draft example changed')
    pair_table(rows,spec)


def pair_table(rows,spec):
    by_id={r['id']:r for r in rows}
    pairs=[]
    for s in spec['scenarios']:
        for v in ('v1','v2'):
            for kind,left,right in [('primary_TA_minus_OA','TA','OA'),('entity_queried','TQ','OQ'),
                                    ('attribute_target','TQ','TA'),('attribute_other','OQ','OA')]:
                pairs.append(dict(kind=kind,left=f"{s['id']}_{left}_{v}",right=f"{s['id']}_{right}_{v}"))
        for c in spec['cells']:
            pairs.append(dict(kind='candidate_value',left=f"{s['id']}_{c}_v1",right=f"{s['id']}_{c}_v2"))
    for p in pairs:
        a,b=by_id[p['left']],by_id[p['right']]
        changed=[i+1 for i,(x,y) in enumerate(zip(a['docs'],b['docs'])) if x!=y]
        require(a['question']==b['question'] and changed==[a['candidate_slot']], 'Multi-slot edit')
        if p['kind'].startswith('primary') or p['kind']=='entity_queried':
            words=lambda row:Counter(re.findall(r'[A-Za-z]+|\d+','\n'.join(row['docs'])))
            require(words(a)==words(b),'Entity attachment changes lexical multiset')
        p.update(changed_slot=changed[0])
    require(len(pairs)==72 and sum(p['kind'].startswith('primary') for p in pairs)==12, 'Pair denominator differs')
    return pairs


def ordered_rows(rows,spec):
    by_id={r['id']:r for r in rows}
    prefix=spec['smoke_prefix_ids']
    return [by_id[k] for k in prefix]+sorted([r for r in rows if r['id'] not in prefix],
        key=lambda r:sha('relation-attachment-order-v1|'+r['id']))


def input_packet(rows):
    ordered=sorted(rows,key=lambda r:sha('relation-input-review-v1|'+r['id']))
    packet=dict(items=[dict(item_id=f'I{i:03d}',question=r['question'],documents=r['docs'])
        for i,r in enumerate(ordered,1)])
    mapping={r['id']:f'I{i:03d}' for i,r in enumerate(ordered,1)}
    page=['<!doctype html><meta charset="utf-8"><title>Input review</title>',
          '<h1>Fictional archive inputs</h1><p>Question and five documents only; no model outputs.</p>']
    for item in packet['items']:
        page.append('<article><h2>'+item['item_id']+'</h2><p>'+html.escape(item['question'])+'</p>')
        for i,d in enumerate(item['documents'],1):
            page.append(f'<p><strong>D{i}</strong> '+html.escape(d)+'</p>')
        page.append('</article>')
    return packet,mapping,'\n'.join(page)+'\n'


def prepare(run=DEFAULT,write=False):
    require(run.resolve()==DEFAULT.resolve(),'Use only the dedicated relation attachment run')
    original_state()
    spec=read(SPEC)
    rows,worlds=make_materials(spec)
    review=read(REVIEW)
    require(review['history_exposed'] is True and review['independent_gold'] is False
            and review['materials_sha256']==sha(encoded(rows).decode())
            and review['reviewed_ids']==[r['id'] for r in rows], 'Author review missing or mismatched')
    e,tokenizer,info=runtime()
    ordered=ordered_rows(rows,spec)
    prompts=[]
    for row in ordered:
        prompt=e.render_input(renderer_inputs(row),'free_answer','chat',tokenizer)
        ids=e.encode(tokenizer,prompt,'chat')['input_ids']
        require(len(ids)+128<=info['context_tokens'],'Context overflow')
        require(re.findall(r'K-\d{5}',prompt)==[row['displayed_candidate']], 'Rendered value leak')
        require(not any(marker in prompt for marker in [row['id'],'worlds','witness_alternative',
            'primary_TA_minus_OA','displayed_candidate','author_mode']), 'Coordinator marker leaked')
        prompts.append(dict(id=row['id'],input_tokens=len(ids),prompt_sha256=sha(prompt),
            input_token_ids_sha256=sha(json.dumps(ids))))
    implementation=['scripts/relation_attachment_study.py','scripts/run_relation_attachment_study.sh',
        'tests/test_relation_attachment_study.py','scripts/behavior_binding_study.py',
        'scripts/evidence_experiment.py','scripts/small_repro.py','scripts/prompt_baseline.py',
        'scripts/analyze_prompt_baseline.py','scripts/classification_semantic_baseline.py',
        'scripts/classification_prompt_search.py','code/prompts.py',
        'prompts/prompt_robustness_P0_P5.json','configs/local.env']
    sources=[SPEC,DESIGN,RUBRIC,REVIEW,EXAMPLES,core.MODEL_REFERENCE,BUDGET,FIT_SEAL,OLD_LABELS]
    eos=read(Path(info['model'])/'generation_config.json')['eos_token_id']
    protocol=dict(task='fictional_relation_attachment_behavior_v1',**info,format='chat',
        instruction=e.FREE_INSTRUCTION,do_sample=False,num_beams=1,use_cache=True,logits_to_keep=1,
        max_new_tokens=128,total_generation_budget=48,scenarios=6,sufficient_TQ=12,insufficient=36,
        primary_pairs=12,extra_smoke_generations=0,new_probe_fits=0,no_hidden_state_collection=True,
        independent_semantic_approval=False,collection_allowed=True,original_formal_gate_changed=False,
        original_fit_budget_remaining=0,ordered_ids=[r['id'] for r in ordered],
        smoke_prefix_ids=spec['smoke_prefix_ids'],eos_token_ids=eos if isinstance(eos,list) else [eos],
        implementation_sha256={p:digest(ROOT/p) for p in implementation},
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sources})
    lengths=[r['input_tokens'] for r in prompts]
    preflight=dict(status='prepared_not_started',cells=48,scenarios=6,
        counts_by_cell=dict(Counter(r['condition'] for r in rows)),smoke_cells_included=4,
        input_tokens_min=min(lengths),input_tokens_max=max(lengths),total_input_tokens=sum(lengths),
        reserved_output_tokens=6144,no_model_weights_loaded=True,no_probe_loaded=True,no_gpu_calls=True,
        prompts=prompts)
    plan=dict(status='prepared_for_user_launch',launch_actor='user',max_answers=48,
        collection_allowed=True,semantic_independent_approval=False,original_formal_gate_changed=False,
        original_fit_budget_remaining=0,ordered_ids=protocol['ordered_ids'],
        smoke_prefix_ids=protocol['smoke_prefix_ids'],main_contrast='TA minus OA,12 pairs in6 scenarios',
        behavior_scoring='Unreviewed; all rates null; no keyword-only scoring')
    packet,mapping,page=input_packet(rows)
    template=dict(reviewer='',history_exposed=None,independent_gold=False,
        packet_sha256=sha(encoded(packet).decode()),ratings=[dict(item_id=r['item_id'],status='unreviewed',
        requested_relation_supported='unknown',rationale='',input_citations=[]) for r in packet['items']])
    outputs=[('materials/inputs.json',rows),('coordinator/witnesses.json',worlds),
        ('coordinator/pairs.json',pair_table(rows,spec)),('protocol.json',protocol),('preflight.json',preflight),
        ('collection_plan.json',plan),('input_review/packet.json',packet),
        ('coordinator/input_mapping.json',mapping),('input_review/ratings_template.json',template)]
    for name,value in outputs:
        save(run/name,value,immutable=True,verify=not write)
    target=run/'input_review/inputs.html'
    data=page.encode()
    if not write or target.exists():
        require(target.is_file() and target.read_bytes()==data,'Frozen input HTML mismatch')
    else:
        target.write_bytes(data)
    return ordered,protocol,tokenizer


def validate_cache(run,rows,protocol,tokenizer):
    import evidence_experiment as e
    path=run/'predictions.json'
    ph=digest(run/'protocol.json')
    records=[]
    if path.exists():
        cache=read(path)
        require(cache['protocol_sha256']==ph,'Prediction protocol mismatch')
        records=cache['records']
    require(len(records)<=len(rows)==48,'Cache exceeds fixed48')
    attempts=sorted((run/'generation_attempts').glob('*'))
    require(len(attempts)==len(records) and all(p.is_file() and p.suffix=='.json' for p in attempts),
            'Uncommitted generation attempt or orphan file; do not regenerate')
    vocab_size=len(tokenizer)  # Query once, not once per generated token.
    for i,(row,record) in enumerate(zip(rows,records)):
        require(attempts[i].name==f'{i:04d}.json' and read(attempts[i])==dict(id=row['id'],protocol_sha256=ph),
                'Attempt order/protocol differs')
        require(all(record[k]==row[k] for k in ['id','original_id','condition','variant']), 'Cache metadata/order differs')
        prompt=e.render_input(renderer_inputs(row),'free_answer','chat',tokenizer)
        ids=e.encode(tokenizer,prompt,'chat')['input_ids']
        require(record['prompt_sha256']==sha(prompt) and record['input_tokens']==len(ids)
                and record['input_token_ids_sha256']==sha(json.dumps(ids)), 'Cached input mismatch')
        tokens=record['generated_token_ids']
        require(isinstance(tokens,list) and 1<=len(tokens)<=128
                and all(type(t) is int and 0<=t<vocab_size for t in tokens), 'Invalid output tokens')
        require(not any(t in protocol['eos_token_ids'] for t in tokens[:-1]), 'Tokens after EOS')
        raw=tokenizer.decode(tokens,skip_special_tokens=True)
        require(raw==record['raw_output'] and sha(raw)==record['raw_output_sha256'], 'Cached output mismatch')
        ended=tokens[-1] in protocol['eos_token_ids']
        require(record['generated_tokens']==len(tokens) and record['ended_with_eos'] is ended
                and record['hit_output_limit'] is (len(tokens)==128 and not ended), 'Cached stop mismatch')
        require(ended or len(tokens)==128,'Unexpected early stop')
        require(type(record['elapsed_seconds']) in [int,float] and math.isfinite(record['elapsed_seconds'])
                and record['elapsed_seconds']>=0,'Invalid timing')
    return records


def collect(run,rows,protocol,tokenizer):
    import evidence_experiment as e
    from classification_semantic_baseline import assert_gpu_idle
    records=validate_cache(run,rows,protocol,tokenizer)
    if len(records)>=4:
        smoke_gate(run,records)
    model=None
    try:
        for row in rows[len(records):]:
            if model is None:
                assert_gpu_idle()
                model=e.load_model(protocol['model'])
            index=len(records)
            marker=run/f'generation_attempts/{index:04d}.json'
            require(not marker.exists(),'Uncommitted attempt; explicit inspection required')
            save(marker,dict(id=row['id'],protocol_sha256=digest(run/'protocol.json')),immutable=True)
            record=generate(model,tokenizer,row,protocol)
            records.append(record)
            save(run/'predictions.json',dict(protocol_sha256=digest(run/'protocol.json'),records=records))
            save(run/'progress.json',dict(status='running',completed=len(records),planned=48,
                last_saved_at=record['completed_at']))
            print(f'relation attachment {len(records)}/48 {row["id"]} saved',flush=True)
            if len(records)==4:
                validate_cache(run,rows,protocol,tokenizer)
                smoke_gate(run,records)
    except BaseException as error:
        save(run/'last_failure.json',dict(completed=len(records),error=repr(error),
            no_automatic_regeneration=True,recorded_at=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        if model is not None:
            del model
            import torch
            torch.cuda.empty_cache()


def finish(run,rows,protocol,tokenizer,verify=False):
    records=validate_cache(run,rows,protocol,tokenizer)
    require(len(records)==48,'Completion requires all48 cached answers')
    smoke_gate(run,records,verify=verify)
    by_id={r['id']:r for r in records}
    anonymous=sorted(rows,key=lambda r:sha('relation-behavior-review-v1|'+r['id']))
    packet=dict(items=[dict(item_id=f'R{i:03d}',question=r['question'],documents=r['docs'],
        answer=by_id[r['id']]['raw_output']) for i,r in enumerate(anonymous,1)])
    mapping={r['id']:f'R{i:03d}' for i,r in enumerate(anonymous,1)}
    template=dict(reviewer='',history_exposed=None,independent_gold=False,
        packet_sha256=sha(encoded(packet).decode()),ratings=[dict(item_id=r['item_id'],status='unreviewed',
        **{field:'unknown' for field in FIELDS},rationale='',input_citations=[],output_citations=[])
        for r in packet['items']])
    summary=dict(status='collection_complete_behavior_unreviewed',completed=48,scenarios=6,
        counts_by_cell=dict(Counter(r['condition'] for r in records)),generations=48,
        extra_smoke_generations=0,new_probe_fits=0,probe_loaded=False,hidden_states_collected=False,
        independent_semantic_approval=False,input_tokens=sum(r['input_tokens'] for r in records),
        output_tokens=sum(r['generated_tokens'] for r in records),
        empty_outputs=sum(not r['raw_output'].strip() for r in records),
        ended_with_eos=sum(r['ended_with_eos'] for r in records),
        hit_output_limit=sum(r['hit_output_limit'] for r in records),behavior_rows_reviewed=0,
        primary_TA_minus_OA=None,all_I_substantive_answer_rate=None,TQ_supported_answer_rate=None,
        historical_failure_record_present=(run/'last_failure.json').exists())
    for name,value in [('behavior_review/packet.json',packet),('coordinator/behavior_mapping.json',mapping),
            ('behavior_review/ratings_template.json',template),('reports/collection.json',summary),
            ('completion.json',dict(status=summary['status'],protocol_sha256=digest(run/'protocol.json'),
                predictions_sha256=digest(run/'predictions.json'),completed=48)),
            ('progress.json',dict(status=summary['status'],completed=48,planned=48,last_saved_at=records[-1]['completed_at']))]:
        save(run/name,value,immutable=name!='progress.json',verify=verify)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['prepare','verify','run','finish','verify-results','all'],default='verify')
    args=parser.parse_args()
    if args.stage in ['verify','verify-results']:
        rows,protocol,tokenizer=prepare(write=False)
        result=finish(DEFAULT,rows,protocol,tokenizer,verify=True) if args.stage=='verify-results' else dict(
            stage='verify',prepared_cells=48,generated=len(read(DEFAULT/'predictions.json')['records'])
            if (DEFAULT/'predictions.json').exists() else 0,no_new_gpu=True)
        print(json.dumps(result))
    else:
        import evidence_experiment as e
        with e.legacy.run_lock(DEFAULT):
            rows,protocol,tokenizer=prepare(write=args.stage=='prepare')
            if args.stage in ['run','all']:
                collect(DEFAULT,rows,protocol,tokenizer)
            if args.stage in ['finish','all']:
                print(json.dumps(finish(DEFAULT,rows,protocol,tokenizer)))
            elif args.stage=='prepare':
                print(json.dumps(dict(stage='prepare',cells=48,scenarios=6,gpu_calls=0,new_fits=0)))


if __name__=='__main__':
    main()
