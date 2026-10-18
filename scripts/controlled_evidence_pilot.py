"""Frozen-probe, matched-evidence development pilot. GPU launch belongs to user."""

import argparse
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

import numpy as np

import controlled_evidence_materials as m
import classification_semantic_baseline as s
import free_answer_study as free
import free_answer_review as review

e = s.e
ROOT = m.ROOT
DEFAULT = ROOT/'runs/qwen2.5-3b-controlled-evidence-pilot-v1'
SMOKE = ROOT/'runs/qwen2.5-3b-controlled-evidence-pilot-smoke-v1'
PROBE_SOURCE = ROOT/'runs/qwen2.5-3b-free-answer-study'
TIMING_SOURCE = ROOT/'docs/records/2026-10-09-free-answer-generation-verified.json'
require = m.require


def render(row, task, tokenizer):
    if task == 'free_answer':
        return e.render_input(row, 'free_answer', 'chat', tokenizer)
    return s.old.render(row, e.read_json(s.PROMPTS)['rules'], tokenizer)


def probe_resources(model):
    old = e.read_json(PROBE_SOURCE/'protocol.json')
    require(old['model'] == model and old['instructions']['free_answer'] == e.FREE_INSTRUCTION,
            'Frozen probe model/instruction mismatch')
    require(old['feature_convention'] == e.FEATURE_CONVENTION, 'Feature convention differs')
    args = argparse.Namespace(run_dir=PROBE_SOURCE)
    probe, fingerprint = free.load_probe(args, 'chat', m.digest(PROBE_SOURCE/'protocol.json'))
    require(probe['layer'] == 28 and list(probe['router'].classes_) == [0,1,2], 'Expected fixed chat L28 probe')
    require(probe['scaler'].n_features_in_ == 2048, 'Expected2048-dimensional probe')
    files = [PROBE_SOURCE/'protocol.json', PROBE_SOURCE/'chat/probe/probe.json',
             PROBE_SOURCE/'chat/probe/probe.pkl', PROBE_SOURCE/'chat/train/states.json',
             PROBE_SOURCE/'chat/val/states.json']
    hashes = {str(p.relative_to(ROOT)): m.digest(p) for p in files}
    require(hashes['runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'] == fingerprint, 'Probe hash differs')
    return probe, hashes, old


def predict_probe(probe, states):
    x = probe['scaler'].transform(states[probe['layer']][None].astype(np.float32))
    probability = probe['router'].predict_proba(x)[0]
    require(np.isfinite(probability).all(), 'Nonfinite probe probabilities')
    classes = probe['router'].classes_
    return dict(probe_pred=e.MODES[int(classes[np.argmax(probability)])],
                probe_probabilities={e.MODES[int(c)]: float(p) for c,p in zip(classes, probability)},
                probe_layer_zero_based=int(probe['layer']), probe_decision_pre_first_token=True)


def make_protocol(args, spec, rows, material_values, probe_hashes, old_protocol):
    files = ['scripts/controlled_evidence_pilot.py', 'scripts/controlled_evidence_materials.py',
             'scripts/run_controlled_evidence_pilot.sh', 'scripts/run_controlled_evidence_pilot_review.sh',
             'scripts/verify_controlled_evidence_pilot.py', 'prompts/controlled_evidence_pilot_v1.json',
             'scripts/evidence_experiment.py', 'scripts/free_answer_study.py',
             'scripts/free_answer_review.py', 'scripts/classification_semantic_baseline.py',
             'scripts/classification_prompt_search.py', 'scripts/small_repro.py',
             'scripts/prompt_baseline.py', 'scripts/analyze_prompt_baseline.py', 'code/prompts.py',
             'prompts/baseline_prompts.json', 'prompts/classification_semantic_v1.json', 'configs/local.env']
    signature = e.repro.feature_spec(argparse.Namespace(model=args.model, template='P0'), rows, m.SOURCE)
    old_signature = old_protocol['reference_specs']['val']
    for key in ['model', 'model_files', 'weights', 'template_sha256', 'renderer_sha256', 'render_policy']:
        require(signature[key] == old_signature[key], f'Frozen probe backbone differs: {key}')
    return dict(schema_version=1, task='controlled_evidence_development_pilot', model=args.model,
                smoke=args.smoke, specification=spec, selected_ids=[r['id'] for r in rows],
                material_sha256={k: e.text_hash(v) for k,v in material_values.items()},
                implementation_sha256={p: m.digest(ROOT/p) for p in files}, probe_source_sha256=probe_hashes,
                source_val_sha256=m.digest(m.SOURCE), backbone_signature=signature,
                generation_config_sha256=m.digest(Path(args.model)/'generation_config.json'),
                tokenizer_chat_policy='Native system/user template; add generation prompt; no extra special tokens',
                runtime_versions={n: e.version(n) for n in ['torch','transformers','numpy','scikit-learn']},
                free_instruction=e.FREE_INSTRUCTION,
                classification_instruction=e.read_json(s.PROMPTS)['rules'],
                generation=dict(dtype='bfloat16', attention='sdpa', greedy=True, beams=1,
                                free_tokens=128, classification_tokens=8, classification_constraint='label trie plus EOS'),
                feature_convention=e.FEATURE_CONVENTION, probe_feedback=False,
                no_training='Frozen existing chat L28 probe, no fitting/calibration/layer or threshold selection',
                calibration_limit='Original layer selection and sigmoid calibration used the whole original val, including these10 base questions. New authored variants are development diagnostics, not held-out probe generalization; transferred probabilities are not recalibrated for this distribution.',
                behavior_rubric=review.RUBRIC,
                analysis='S/I/C30 primary; D10 separately, paired within original question; no pilot candidate selection or population inference',
                technical_smoke='One fixed longest-text base, all4 variants; free text nonempty/EOS/not truncated and4 valid labels. No semantic-accuracy gate.',
                exposure='Authored variants of10 previously reviewed validation bases; source history exposed. Not independent gold/confirmation.',
                distribution_limit='Two short authored targets and three complete shortest source-refuse distractors; clarified questions and explicit exclusivity. Length/wording shifts are measured, not eliminated.',
                no_test_access='No original test rows, test predictions or confirmation inputs opened. Old durable aggregate timing only.',
                original_screening='Existing no_qualified_baseline and thresholds unchanged; this pilot cannot qualify a baseline.')


def preflight(args, spec, rows, tokenizer, grammar):
    context = e.read_json(Path(args.model)/'config.json')['max_position_embeddings']
    lengths = {}
    by_id = {}
    for task, budget in [('free_answer',128), ('classification',8)]:
        values = {r['id']: len(e.encode(tokenizer, render(r,task,tokenizer),'chat')['input_ids']) for r in rows}
        require(max(values.values()) + budget <= context, 'Context overflow: do not truncate evidence')
        lengths[task] = dict(instances=len(rows), max_input_tokens=max(values.values()),
                             mean_input_tokens=sum(values.values())/len(values), output_budget=budget)
        by_id[task] = values
    require(grammar.maximum_tokens <= 8, 'Grammar budget too short')
    history = e.read_json(TIMING_SOURCE)['formats']['chat']['test']
    effective_seconds_per_token = history['elapsed_seconds_sum']/(history['n_instances']*history['output_tokens']['mean'])
    # Includes8 smoke calls and a conservative4x throughput allowance, plus model loading/IO.
    max_tokens = (40+4)*128 + (40+4)*3
    planning = [max(5, math.ceil(max_tokens*effective_seconds_per_token/60+3)),
                max(20, math.ceil(max_tokens*effective_seconds_per_token*4/60+6))]
    groups = {}
    for row in rows:
        groups.setdefault(row['original_id'], {})[row['condition']] = row
    deltas = []
    for oid, group in groups.items():
        for condition in ('I','C','D'):
            left, right = group['S'], group[condition]
            deltas.append(dict(original_id=oid, comparison=condition+'_minus_S',
                               character_delta=sum(map(len,right['docs']))-sum(map(len,left['docs'])),
                               free_input_token_delta=by_id['free_answer'][right['id']]-by_id['free_answer'][left['id']],
                               classification_input_token_delta=by_id['classification'][right['id']]-by_id['classification'][left['id']]))
    return dict(status='cpu_preflight_passed', input_lengths=lengths, per_input_tokens=by_id,
                length_deltas=deltas, context_tokens=context, feature_shape=[36,2048],
                expected_free_generations=len(rows), expected_classifications=len(rows),
                grammar_max_tokens=grammar.maximum_tokens,
                historical_effective_seconds_per_token=effective_seconds_per_token,
                historical_timing_source=str(TIMING_SOURCE.relative_to(ROOT)),
                historical_timing_sha256=m.digest(TIMING_SOURCE),
                whole_smoke_plus_full_planning_minutes=planning,
                timing_note='Capacity planning from old aggregate chat timing,128-token ceiling,4x allowance and load/IO; not a new GPU benchmark or deadline. User launches.')


def prepare(args):
    spec, all_rows, judgments, provenance = m.build()
    rows = [r for r in all_rows if r['original_id'] == spec['smoke_base']] if args.smoke else all_rows
    keys = {r['id'] for r in rows}
    judgments = [j for j in judgments if j['id'] in keys]
    provenance = [p for p in provenance if p['original_id'] in {r['original_id'] for r in rows}]
    materials = m.material_artifacts(rows,judgments,provenance)
    probe, probe_hashes, old_protocol = probe_resources(args.model)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    grammar = s.LabelGrammar(tokenizer,s.eos_ids(args.model,tokenizer))
    protocol = make_protocol(args,spec,rows,materials,probe_hashes,old_protocol)
    e.freeze(args.run_dir/'protocol.json',protocol)
    for name, value in materials.items():
        m.write_new(args.run_dir/'materials'/name,value)
    seal=dict(protocol_sha256=m.digest(args.run_dir/'protocol.json'),
              inputs_sha256=m.digest(args.run_dir/'materials/inputs.json'),
              judgments_sha256=m.digest(args.run_dir/'materials/input_judgments.json'),
              reviewed_inputs=len(rows),document_slots=len(rows)*5,
              reviewer='current_coordinating_assistant_author_history_exposed',
              review_date='2026-10-18',independent_gold=False,
              scope='Explicit authored alternatives and retained full distractors reviewed before new GPU output; assembly/citation checks do not independently validate semantics.')
    m.write_new(args.run_dir/'materials/review_seal.json',m.json_text(seal))
    pre = preflight(args,spec,rows,tokenizer,grammar)
    m.write_new(args.run_dir/'preflight.json',m.json_text(pre))
    if not (args.run_dir/'progress.json').exists():
        e.repro.write_json(args.run_dir/'progress.json',dict(status='prepared_not_started', free_saved=0,
                           classification_saved=0,target_each=len(rows),protocol_sha256=m.digest(args.run_dir/'protocol.json')))
    return rows,probe,tokenizer,grammar,protocol,pre


def checkpoint_spec(base, task):
    return dict(protocol_sha256=m.digest(base/'protocol.json'),task=task,format='chat')


def cache(base,task,rows,tokenizer,grammar,probe,model):
    path=base/task/'predictions.json'
    if not path.exists():
        return []
    value=e.read_json(path)
    require(value['spec']==checkpoint_spec(base,task) and len(value['records'])<=len(rows),'Cache spec/count changed')
    records=value['records']
    budget=128 if task=='free_answer' else 8
    for i,(row,record) in enumerate(zip(rows,records)):
        require(all(record[k]==row[k] for k in ['id','original_id','condition','true_mode']),'Cache identity/order changed')
        text=render(row,task,tokenizer)
        require(record['prompt_sha256']==e.text_hash(text),'Cached prompt differs')
        require(record['input_tokens']==len(e.encode(tokenizer,text,'chat')['input_ids']),'Cached input length differs')
        tokens=record['generated_token_ids']
        require(isinstance(tokens,list) and all(type(t) is int for t in tokens) and
                len(tokens)==record['generated_tokens'] and 0<len(tokens)<=budget,'Invalid cached tokens')
        require(tokenizer.decode(tokens,skip_special_tokens=True)==record['raw_output'],'Token/text differs')
        require(record['raw_output_sha256']==e.text_hash(record['raw_output']),'Cached output hash differs')
        eos=grammar.eos_ids
        require(not any(t in eos for t in tokens[:-1]),'Tokens after EOS')
        ended=tokens[-1] in eos
        require(record['ended_with_eos']==ended and record['hit_output_limit']==(len(tokens)==budget and not ended),
                'Cached termination flags differ')
        if task=='classification':
            mode=s.parse_output(grammar,tokenizer,tokens,record['raw_output'])
            require(record['pred_mode']==mode and record['technical_valid']==(mode is not None),'Cached label differs')
            require(record['strict_format_pass']==(e.legacy.parse_label(record['raw_output']) is not None),'Cached strict format differs')
        else:
            relative=f'features/{i:04d}.npy'
            require(record['feature_file']==relative,'Unexpected feature path')
            feature=base/task/relative
            require(m.digest(feature)==record['feature_sha256'],'Feature hash differs')
            states=np.load(feature,allow_pickle=False)
            require(states.shape==(36,2048) and states.dtype==np.float16 and np.isfinite(states).all()
                    and not np.any(np.all(states==0,axis=1)),'Invalid states')
            expected=predict_probe(probe,states)
            for field in ['probe_pred','probe_layer_zero_based','probe_decision_pre_first_token']:
                require(record[field]==expected[field],'Cached pre-generation probe differs')
            require(set(record['probe_probabilities'])==set(e.MODES),'Missing probe classes')
            require(all(np.isclose(record['probe_probabilities'][k],expected['probe_probabilities'][k],rtol=0,atol=1e-10)
                        for k in e.MODES),'Cached probe probabilities differ')
    return records


def generate_free(model,tokenizer,row,probe,grammar):
    import torch
    from transformers import GenerationConfig
    text=render(row,'free_answer',tokenizer)
    inputs=e.encode(tokenizer,text,'chat',return_tensors='pt').to(model.device)
    length=inputs.input_ids.shape[1]
    require(length+128<=model.config.max_position_embeddings,'Context overflow')
    config=GenerationConfig(max_new_tokens=128,do_sample=False,num_beams=1,use_cache=True,
                            eos_token_id=grammar.eos_ids,bos_token_id=model.generation_config.bos_token_id,
                            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    decision={}
    def before_first_token(h):
        require(not decision,'Probe called multiple times')
        decision.update(predict_probe(probe,h))
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.monotonic()
    with e.LastPromptCapture(model,on_prefill=before_first_token) as capture,torch.inference_mode():
        output=model.generate(**inputs,generation_config=config,logits_to_keep=1)
    require(bool(decision),'No pre-generation decision')
    states=capture.array()
    tokens=output[0,length:].tolist();raw=tokenizer.decode(tokens,skip_special_tokens=True)
    torch.cuda.synchronize()
    require(bool(tokens),'No output tokens')
    return dict(id=row['id'],original_id=row['original_id'],condition=row['condition'],true_mode=row['true_mode'],
                prompt_sha256=e.text_hash(text),input_tokens=length,raw_output=raw,raw_output_sha256=e.text_hash(raw),
                generated_token_ids=tokens,generated_tokens=len(tokens),ended_with_eos=tokens[-1] in grammar.eos_ids,
                hit_output_limit=len(tokens)==128 and tokens[-1] not in grammar.eos_ids,
                elapsed_seconds=time.monotonic()-start,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                completed_at=datetime.now(timezone.utc).isoformat(),**decision),states


def infer(args,rows,probe,tokenizer,grammar):
    model=None
    try:
        for task in ['free_answer','classification']:
            records=cache(args.run_dir,task,rows,tokenizer,grammar,probe,args.model)
            if len(records)==len(rows):
                continue
            if model is None:
                try:
                    s.assert_gpu_idle()
                    model=e.load_model(args.model)
                except Exception as error:
                    e.repro.write_json(args.run_dir/'last_failure.json',dict(stage='model_load_or_gpu_guard',task=task,id=None,error=str(error)))
                    raise
            for row in rows[len(records):]:
                try:
                    if task=='free_answer':
                        record,states=generate_free(model,tokenizer,row,probe,grammar)
                        relative=f'features/{len(records):04d}.npy'
                        e.save_array(args.run_dir/task/relative,states)
                        record.update(feature_file=relative,feature_sha256=m.digest(args.run_dir/task/relative))
                    else:
                        record=s.generate(model,tokenizer,row,e.read_json(s.PROMPTS)['rules'],grammar)
                        record.update(condition=row['condition'],ended_with_eos=record['generated_token_ids'][-1] in grammar.eos_ids)
                    records.append(record)
                    e.repro.write_json(args.run_dir/task/'predictions.json',dict(spec=checkpoint_spec(args.run_dir,task),records=records))
                    e.repro.write_json(args.run_dir/'progress.json',dict(status='running',task=task,saved_in_task=len(records),
                                       target_each=len(rows),last_saved_id=row['id'],protocol_sha256=m.digest(args.run_dir/'protocol.json')))
                    print(f'{task} [{len(records)}/{len(rows)}] {row["id"]}',flush=True)
                except Exception as error:
                    e.repro.write_json(args.run_dir/'last_failure.json',dict(task=task,id=row['id'],error=str(error)))
                    raise
    finally:
        if model is not None:
            del model
            import torch
            torch.cuda.empty_cache()
    e.repro.write_json(args.run_dir/'progress.json',dict(status='generation_complete',free_saved=len(rows),
                       classification_saved=len(rows),protocol_sha256=m.digest(args.run_dir/'protocol.json')))


def technical_gate(rows,free_records,class_records):
    require(len(rows)==len(free_records)==len(class_records)==4,'Smoke needs4 of each task')
    require(set(r['condition'] for r in rows)==set('SICD'),'Smoke needs all4 conditions')
    require(all(r['raw_output'].strip() and r['ended_with_eos'] and not r['hit_output_limit']
                and r['probe_decision_pre_first_token'] for r in free_records),'Free-generation technical smoke failed')
    require(all(r['technical_valid'] and r['strict_format_pass'] and r['ended_with_eos']
                and not r['hit_output_limit'] for r in class_records),'Classification technical smoke failed')
    return dict(status='technical_smoke_passed',free_complete=4,classification_valid=4,semantic_accuracy_gate=False)


def require_full_smoke(args,protocol,probe,tokenizer,grammar):
    require((SMOKE/'protocol.json').exists() and (SMOKE/'smoke_gate.json').exists(),
            'Complete the supplied smoke launcher before full inference')
    saved=e.read_json(SMOKE/'protocol.json')
    require(saved['smoke'] and saved['model']==args.model and
            saved['implementation_sha256']==protocol['implementation_sha256'] and
            saved['probe_source_sha256']==protocol['probe_source_sha256'] and
            saved['specification']==protocol['specification'],'Smoke belongs to a different frozen setup')
    spec,all_rows,_,_=m.build()
    rows=[r for r in all_rows if r['original_id']==spec['smoke_base']]
    gate=technical_gate(rows,cache(SMOKE,'free_answer',rows,tokenizer,grammar,probe,args.model),
                        cache(SMOKE,'classification',rows,tokenizer,grammar,probe,args.model))
    require(gate==e.read_json(SMOKE/'smoke_gate.json'),'Saved smoke gate differs')


def ensure_review(base,rows,records,write):
    path=base/'review/manifest.json'
    if not path.exists():
        if not write:
            raise ValueError('Run analyze once to export review')
        review.export_review(base,{r['id']:r for r in rows},{'chat':records})
    value=e.read_json(path)
    expected=[('chat',r['id'],e.text_hash(r['raw_output'])) for r in records]
    actual=[(r['format'],r['id'],r['raw_output_sha256']) for r in value['items']]
    require(sorted(expected)==sorted(actual) and value['rubric']==review.RUBRIC,'Review manifest/output differs')
    # Frozen exporter always uses this fixed permutation; verify anonymous IDs too.
    order=np.random.default_rng(20261009).permutation(len(records))
    require(all(item['item_id']==f'item_{i+1:04d}' and item['id']==records[int(pos)]['id']
                for i,(item,pos) in enumerate(zip(value['items'],order))),'Review order differs')
    return value['items']


def summarize(rows,free_records,class_records,annotations):
    by_id={r['id']:r for r in rows}
    joined=[dict(r,behavior=copy.deepcopy(annotations.get(('chat',r['id']),{}))) for r in free_records]
    main=[r for r in rows if r['condition']!='D']
    main_keys={r['id'] for r in main}
    main_free=[r for r in joined if r['id'] in main_keys]
    main_class=[r for r in class_records if r['id'] in main_keys]
    main_probe=[dict(r,pred_mode=r['probe_pred']) for r in main_free]
    behavior=review.behavior_summary(main_free)
    control=[r for r in joined if r['id'] not in main_keys]
    control_behavior=review.behavior_summary(control)
    groups={}
    labels={r['id']:r['pred_mode'] for r in class_records}
    for record in joined:
        groups.setdefault(record['original_id'],{})[by_id[record['id']]['condition']]=record
    pairs=[]
    for oid,group in groups.items():
        require(set(group)==set('SICD'),'Incomplete matched quartet')
        support,insufficient,conflict,unrelated=[group[c] for c in 'SICD']
        pairs.append(dict(original_id=oid,ids={c:group[c]['id'] for c in 'SICD'},
                          probe_predictions={c:group[c]['probe_pred'] for c in 'SICD'},
                          classification_predictions={c:labels[group[c]['id']] for c in 'SICD'},
                          probe_S_answer_I_refuse=support['probe_pred']=='answer' and insufficient['probe_pred']=='refuse',
                          probe_S_answer_C_conflict=support['probe_pred']=='answer' and conflict['probe_pred']=='conflict',
                          I_refuse_probability_minus_S=insufficient['probe_probabilities']['refuse']-support['probe_probabilities']['refuse'],
                          C_conflict_probability_minus_S=conflict['probe_probabilities']['conflict']-support['probe_probabilities']['conflict'],
                          D_same_probe=support['probe_pred']==unrelated['probe_pred'],
                          D_probe_total_variation=.5*sum(abs(support['probe_probabilities'][k]-unrelated['probe_probabilities'][k]) for k in e.MODES),
                          D_same_classification=labels[support['id']]==labels[unrelated['id']],
                          behavior_by_condition={c:group[c]['behavior'] for c in 'SICD'}))
    control_fields={}
    for field in review.FIELDS:
        known=[p for p in pairs if p['behavior_by_condition']['S'].get(field) is not None
               and p['behavior_by_condition']['D'].get(field) is not None]
        equal=sum(p['behavior_by_condition']['S'][field]==p['behavior_by_condition']['D'][field] for p in known)
        unknown=len(pairs)-len(known)
        control_fields[field]=dict(denominator=len(pairs),known_equal=equal,unknown_pairs=unknown,
                                   rate=equal/len(pairs) if not unknown else None,
                                   lower_bound=equal/len(pairs),upper_bound=(equal+unknown)/len(pairs))
    return dict(status='analysis_complete_behavior_pending' if any(
                r['behavior'].get(f) is None for r in joined for f in review.FIELDS) else 'analysis_complete_scored',
                main=dict(instances=len(main),probe=e.classification_metrics(main,main_probe),
                          fixed_classification=e.classification_metrics(main,main_class),behavior=behavior),
                control=dict(instances=len(control),probe_answer_count=sum(r['probe_pred']=='answer' for r in control),
                             classification_answer_count=sum(labels[r['id']]=='answer' for r in control),behavior=control_behavior,
                             same_probe_count=sum(p['D_same_probe'] for p in pairs),
                             same_classification_count=sum(p['D_same_classification'] for p in pairs),behavior_invariance=control_fields),
                paired_by_question=pairs,unknown_behavior_rows=sum(any(r['behavior'].get(f) is None for f in review.FIELDS) for r in joined),
                generation=dict(empty=sum(not r['raw_output'].strip() for r in joined),
                                truncated=sum(r['hit_output_limit'] for r in joined)),
                limitation='Authored and exposed validation-development cases, frozen probe transferred to new wording/short targets; no independent gold, baseline qualification, population inference or hidden-state intervention.')


def analyze(args,rows,probe,tokenizer,grammar,write=True):
    free_records=cache(args.run_dir,'free_answer',rows,tokenizer,grammar,probe,args.model)
    labels=cache(args.run_dir,'classification',rows,tokenizer,grammar,probe,args.model)
    require(len(free_records)==len(labels)==len(rows),'Generation incomplete; resume launch')
    gate=technical_gate(rows,free_records,labels) if args.smoke else None
    manifest=ensure_review(args.run_dir,rows,free_records,write)
    annotation_path=args.annotations or args.run_dir/'annotations.csv'
    annotations=review.load_annotations(annotation_path,manifest,m.digest(args.run_dir/'review/manifest.json'))
    report=summarize(rows,free_records,labels,annotations)
    report.update(protocol_sha256=m.digest(args.run_dir/'protocol.json'),technical_smoke=gate,
                  annotation_file=str(annotation_path),annotation_sha256=m.digest(annotation_path) if annotation_path.exists() else None)
    if write:
        previous=args.run_dir/'reports/pilot.json'
        if previous.exists() and e.read_json(previous)!=report:
            historical=args.run_dir/'reports/history'/m.digest(previous)
            for name in ['pilot.json','pilot.md']:
                source=args.run_dir/'reports'/name
                if source.exists():m.write_new(historical/name,source.read_text())
        if annotation_path.exists():
            m.write_new(args.run_dir/'review/annotation_snapshots'/f'{m.digest(annotation_path)}.csv',annotation_path.read_bytes().decode('utf-8'))
        e.repro.write_json(args.run_dir/'reports/pilot.json',report)
        lines=['# 同题证据对照开发小试验','',report['limitation'],'',
               f'状态：{report["status"]}；未知行为行：{report["unknown_behavior_rows"]}。',
               f'主S/I/C：{report["main"]["instances"]}条；D控制：{report["control"]["instances"]}条，单列。',
               f'探针主表：{report["main"]["probe"]["correct"]}/{report["main"]["instances"]}。',
               f'固定分类对照主表：{report["main"]["fixed_classification"]["correct"]}/{report["main"]["instances"]}。',
               '', '行为率、完整分母上下界、每题概率变化与D不变性见pilot.json；没有评分时不推断行为。']
        (args.run_dir/'reports/pilot.md').write_text('\n'.join(lines)+'\n')
        if gate:e.repro.write_json(args.run_dir/'smoke_gate.json',gate)
        e.repro.write_json(args.run_dir/'progress.json',dict(status=report['status'],free_saved=len(rows),
                           classification_saved=len(rows),protocol_sha256=report['protocol_sha256']))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['check','infer','analyze','all'],default='all')
    parser.add_argument('--run_dir',type=Path,default=DEFAULT)
    parser.add_argument('--model',default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--annotations',type=Path)
    args=parser.parse_args()
    if not args.model:parser.error('Use shell entry or --model')
    args.model=str(Path(args.model).resolve());args.run_dir=e.resolve(args.run_dir)
    if args.annotations:args.annotations=e.resolve(args.annotations)
    require(args.run_dir.is_relative_to(ROOT/'runs') and not args.run_dir.is_relative_to(PROBE_SOURCE),
            'Use a new pilot run directory under runs/')
    require(not args.smoke or args.run_dir!=DEFAULT,'Smoke requires a separate directory')
    with e.legacy.run_lock(args.run_dir):
        rows,probe,tokenizer,grammar,protocol,pre=prepare(args)
        if args.stage=='check':
            print(json.dumps(dict(status=e.read_json(args.run_dir/'progress.json')['status'],inputs=len(rows),
                                  lengths=pre['input_lengths'],planning_minutes=pre['whole_smoke_plus_full_planning_minutes']),
                             ensure_ascii=False,indent=2))
            return
        if args.stage in ['all','infer']:
            if not args.smoke:require_full_smoke(args,protocol,probe,tokenizer,grammar)
            infer(args,rows,probe,tokenizer,grammar)
        if args.stage in ['all','analyze']:
            report=analyze(args,rows,probe,tokenizer,grammar)
            print('Analysis complete: '+report['status'],flush=True)


if __name__=='__main__':main()
