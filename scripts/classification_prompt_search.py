"""Predeclared validation-only prompt selection, resumable per generated instance.

Never loads diagnostic/confirmation test data. GPU inference is user-started.
The original classification experiment and shared renderer stay unchanged.
"""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time

import evidence_experiment as e

ROOT = e.PROJECT
PROMPTS = ROOT / 'prompts/classification_validation_v1.json'
REVIEW = ROOT / 'runs/qwen2.5-3b-free-answer-study/review/independent-semantic-2026-10-11'


def render(row, instruction, tokenizer):
    body = e.render_prompt('P0', row['question'], row['docs'], instruction='')
    if not body.endswith('Answer:'):
        raise ValueError('P0 suffix changed')
    body = body[:-len('Answer:')] + 'Label:'
    return tokenizer.apply_chat_template([
        {'role': 'system', 'content': instruction},
        {'role': 'user', 'content': body}], tokenize=False, add_generation_prompt=True)


def sources(args):
    manifest = e.read_json(args.reference / 'data/manifest.json')
    paths = {s: args.reference / 'data' / f'instances_{s}.jsonl' for s in ['train', 'val']}
    for split, path in paths.items():
        if e.repro.digest_file(path) != manifest['splits'][split]['sha256']:
            raise ValueError(f'{split} data fingerprint mismatch')
    train = e.repro.load_rows(paths['train'])
    val = e.repro.load_rows(paths['val'])
    e.validate_rows(train, 'train')
    groups = e.validate_rows(val, 'val')
    if {r['original_id'] for r in train} & set(groups) or {r['question'] for r in train} & {r['question'] for r in val}:
        raise ValueError('Training/validation overlap')
    spec = e.repro.feature_spec(argparse.Namespace(model=args.model, template='P0'), val, paths['val'])
    if spec != e.read_json(args.reference / 'activations/meta_P0_val.json')['spec']:
        raise ValueError('Validation/model/renderer mismatch with fixed reference')
    if args.limit_questions is not None:
        if not 1 <= args.limit_questions <= len(groups):
            raise ValueError('Invalid smoke question count')
        keep = set(list(groups)[:args.limit_questions])
        val = [r for r in val if r['original_id'] in keep]
    return val, spec


def protocol(args, rows, spec, config):
    files = [Path(__file__), PROMPTS, ROOT / 'scripts/evidence_experiment.py',
             ROOT / 'scripts/small_repro.py', ROOT / 'scripts/prompt_baseline.py',
             ROOT / 'scripts/analyze_prompt_baseline.py', ROOT / 'code/prompts.py']
    return dict(schema_version=2, task='validation_only_classification_prompt_search',
                model=args.model, reference=str(args.reference), split='val',
                selected_ids=[r['id'] for r in rows], source_spec=spec,
                configuration=config,
                code_and_prompt_sha256={str(p.relative_to(ROOT)): e.repro.digest_file(p) for p in files},
                legacy_validation_sha256=e.repro.digest_file(args.baseline),
                legacy_protocol_sha256=e.repro.digest_file(args.baseline.parents[2] / 'protocol.json'),
                generation_config_sha256=e.repro.digest_file(Path(args.model) / 'generation_config.json'),
                runtime_versions={n: e.version(n) for n in ['torch', 'transformers', 'numpy']},
                generation=dict(dtype='bfloat16', attention='sdpa', do_sample=False,
                                num_beams=1, use_cache=True, logits_to_keep=1, max_new_tokens=8),
                parser=dict(primary=e.FIRST_LINE_POLICY, strict='whole_output_single_label_v1',
                            invalid='retained in all denominators'),
                independent_review_gate=str(REVIEW / 'coordinator/readiness.json'),
                review_gate_policy='300 second-context input ratings and 234 behavior scores; disclosed coordinator supplements allowed only for missing behavior assignments, never called independent ratings. Adjudication and source limits disclosed separately.',
                smoke=args.limit_questions is not None,
                test_access='no test split or test predictions are read; no confirmation inference',
                selection_note='Published validation labels are not independently verified semantic gold; selected scores are optimistic.')


def cached(path, spec, rows, instruction, tokenizer):
    if not path.exists():
        return []
    value = e.read_json(path)
    records = value['records']
    if value['spec'] != spec or len(records) > len(rows):
        raise ValueError('Checkpoint settings/count changed; use a new run_dir')
    for row, record in zip(rows, records):
        if row['id'] != record['id'] or row['true_mode'] != record['true_mode']:
            raise ValueError('Checkpoint identity/order mismatch')
        if record['prompt_sha256'] != e.text_hash(render(row, instruction, tokenizer)):
            raise ValueError('Checkpoint prompt mismatch')
        if record['raw_output_sha256'] != e.text_hash(record['raw_output']):
            raise ValueError('Checkpoint output hash mismatch')
        if not isinstance(record['generated_tokens'], int) or not 0 <= record['generated_tokens'] <= 8:
            raise ValueError('Checkpoint output budget mismatch')
        if record['pred_mode'] != e.first_line_label(record['raw_output']) or record['strict_format_pass'] != (e.legacy.parse_label(record['raw_output']) is not None):
            raise ValueError('Checkpoint parsing mismatch')
    return records


def baseline(args, rows, tokenizer):
    value = e.read_json(args.baseline)
    prior_protocol_path = args.baseline.parents[2] / 'protocol.json'
    prior_protocol = e.read_json(prior_protocol_path)
    if value['spec']['protocol_sha256'] != e.repro.digest_file(prior_protocol_path):
        raise ValueError('Legacy protocol hash mismatch')
    if prior_protocol['model'] != args.model or prior_protocol['instructions']['classification'] != e.legacy.INSTRUCTION:
        raise ValueError('Legacy model/instruction mismatch')
    if value['spec']['condition'] != 'chat8' or value['spec']['split'] != 'val':
        raise ValueError('Expected chat8 validation control')
    if prior_protocol['reference_specs']['val'] != e.repro.feature_spec(
            argparse.Namespace(model=args.model, template='P0'),
            e.repro.load_rows(args.reference / 'data/instances_val.jsonl'),
            args.reference / 'data/instances_val.jsonl'):
        raise ValueError('Legacy validation source mismatch')
    full = e.repro.load_rows(args.reference / 'data/instances_val.jsonl')
    checked = e.load_records(args.baseline, value['spec'], full, 'classification', 'chat', tokenizer)
    if len(checked) != len(full):
        raise ValueError('Legacy validation is incomplete')
    lookup = {r['id']: r for r in checked}
    return [lookup[r['id']] for r in rows]


def preflight(args, rows, tokenizer, config):
    context = e.read_json(Path(args.model) / 'config.json')['max_position_embeddings']
    lengths = {}
    for name in config['candidate_order']:
        counts = [len(e.encode(tokenizer, render(r, config['instructions'][name], tokenizer), 'chat')['input_ids']) for r in rows]
        if max(counts) + config['max_new_tokens'] > context:
            raise ValueError(f'{name}: context overflow; no evidence truncated')
        lengths[name] = dict(instances=len(rows), max_input_tokens=max(counts),
                             mean_input_tokens=sum(counts)/len(counts), reserved_output_tokens=8)
    old = baseline(args, rows, tokenizer)
    seconds = sum(r['elapsed_seconds'] for r in old)
    base_minutes = seconds * len(config['candidate_order']) / 60
    return dict(status='cpu_preflight_passed', context_tokens=context, candidates=lengths,
                reused_validation_outputs=len(old), new_generations=len(rows)*len(config['candidate_order']),
                historical_chat8_seconds=seconds,
                runtime_estimate=dict(historical_generation_lower_minutes=base_minutes,
                                      planning_minutes=[round(base_minutes + 1, 1), round(base_minutes*2.5 + 3, 1)],
                                      note='Historical GPU generation timing excludes loading, CPU checks and changed prompt overhead; conservative upper estimate exceeds 10 minutes for full run.'),
                launch_actor='user', independent_review_ready=(REVIEW/'coordinator/readiness.json').exists())


def review_gate():
    path = REVIEW / 'coordinator/readiness.json'
    if not path.exists():
        raise ValueError('Independent item review is unfinished; wait for coordinator/readiness.json')
    value = e.read_json(path)
    status = value.get('status')
    if status not in {'independent_review_verified', 'review_verified_with_coordinator_supplement'} or value.get('evidence_items') != 300 or value.get('behavior_items') != 234:
        raise ValueError('Review readiness is incomplete')
    if status == 'review_verified_with_coordinator_supplement':
        second = value.get('second_review_behavior_items')
        supplement = value.get('coordinator_supplement_behavior_items')
        if (not isinstance(second, int) or not isinstance(supplement, int)
                or second < 0 or supplement <= 0 or second + supplement != 234
                or not value.get('reviewer_independence')):
            raise ValueError('Coordinator supplements must have explicit coverage and exposure disclosure')
    if value.get('packet_sha256') != e.repro.digest_file(REVIEW/'public/protocol.json'):
        raise ValueError('Independent review gate belongs to another packet')
    for filename, digest in value['ratings_sha256'].items():
        if e.repro.digest_file(ROOT/filename) != digest:
            raise ValueError('Independent ratings changed after verification')
    if not value.get('background_exposure_disclosed'):
        raise ValueError('Independent-review limitations must be disclosed')
    return value


def assert_gpu_idle():
    result = subprocess.run(['nvidia-smi', '-i', os.environ.get('CUDA_VISIBLE_DEVICES', '0'),
                             '--query-compute-apps=pid,process_name,used_memory',
                             '--format=csv,noheader'], capture_output=True, text=True, check=True)
    if result.stdout.strip():
        raise RuntimeError('Selected GPU has an active compute process; stop and choose an idle time')


def generate(model, tokenizer, row, instruction):
    import torch
    from transformers import GenerationConfig
    text = render(row, instruction, tokenizer)
    inputs = e.encode(tokenizer, text, 'chat', return_tensors='pt').to(model.device)
    length = inputs.input_ids.shape[1]
    if length + 8 > model.config.max_position_embeddings:
        raise ValueError('Context exceeded; evidence was not truncated')
    eos = model.generation_config.eos_token_id or tokenizer.eos_token_id
    config = GenerationConfig(max_new_tokens=8, do_sample=False, num_beams=1, use_cache=True,
                              eos_token_id=eos, bos_token_id=model.generation_config.bos_token_id,
                              pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
    start = time.monotonic()
    with torch.inference_mode():
        output = model.generate(**inputs, generation_config=config, logits_to_keep=1)
    tokens = output[0, length:]
    raw = tokenizer.decode(tokens, skip_special_tokens=True)
    torch.cuda.synchronize()
    eos_ids = eos if isinstance(eos, list) else [eos]
    return dict(id=row['id'], original_id=row['original_id'], true_mode=row['true_mode'],
                raw_output=raw, raw_output_sha256=e.text_hash(raw), input_tokens=length,
                generated_tokens=len(tokens), hit_output_limit=len(tokens)==8 and int(tokens[-1]) not in eos_ids,
                elapsed_seconds=time.monotonic()-start, peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                completed_at=datetime.now(timezone.utc).isoformat(), prompt_sha256=e.text_hash(text),
                pred_mode=e.first_line_label(raw), strict_format_pass=e.legacy.parse_label(raw) is not None)


def select(metrics, config):
    policy = config['selection']
    eligible = []
    for name in config['candidate_order']:
        m = metrics[name]
        if (m['parse_coverage'] >= policy['minimum_parse_coverage'] and
                m['strict_format_pass_rate'] >= policy['minimum_strict_format_rate'] and
                min(v['recall'] for v in m['per_class'].values()) >= policy['minimum_recall_each_class'] and
                m['classification_false_answer_rate'] <= policy['maximum_classification_false_answer_rate']):
            eligible.append(name)
    def rank(name):
        m = metrics[name]
        return (-m['macro_f1'], m['classification_false_answer_rate'],
                -min(v['recall'] for v in m['per_class'].values()), config['candidate_order'].index(name))
    ranked = sorted(eligible or config['candidate_order'], key=rank)
    return dict(eligible_candidates=eligible, selected_candidate=ranked[0] if eligible else None,
                diagnostic_best_candidate=ranked[0], status='candidate_selected_for_later_confirmation' if eligible else 'no_qualified_baseline')


def analyze(args, rows, config, spec, tokenizer):
    methods = {'legacy_chat8': baseline(args, rows, tokenizer)}
    metrics = {}
    for name in config['candidate_order']:
        path = args.run_dir/name/'predictions.json'
        methods[name] = cached(path, dict(protocol_sha256=spec, candidate=name, split='val'), rows,
                               config['instructions'][name], tokenizer)
        if len(methods[name]) != len(rows):
            raise ValueError(f'{name} incomplete: resume inference')
    for name, records in methods.items():
        metrics[name] = e.classification_metrics(rows, records)
        metrics[name].update(strict_format_pass_rate=sum(r['strict_format_pass'] for r in records)/len(rows),
                             hit_output_limit_count=sum(r['hit_output_limit'] for r in records),
                             empty_output_count=sum(not r['raw_output'].strip() for r in records))
    selection = select(metrics, config)
    if args.limit_questions is not None:
        selection = dict(status='smoke_only_no_selection', selected_candidate=None)
    report = dict(split='val', instances=len(rows), methods=metrics, selection=selection,
                  paired_question_bootstrap={name+'_minus_legacy_chat8':e.bootstrap_pair(rows, methods[name], methods['legacy_chat8']) for name in config['candidate_order']},
                  protocol_sha256=spec, note='Validation is selected on; not independent test evidence. Published labels have semantic quality limitations. No test or confirmation predictions.')
    e.repro.write_json(args.run_dir/'reports/val.json', report)
    lines=['# 验证集提示词比较', '', '| 条件 | Accuracy | Macro-F1 | 分类错误可答率 | 严格格式 | 不足→可答 | 冲突→可答 |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,m in metrics.items():
        lines.append(f"| {name} | {m['accuracy']:.2%} | {m['macro_f1']:.2%} | {m['classification_false_answer_rate']:.2%} | {m['strict_format_pass_rate']:.2%} | {m['refuse_to_answer_count']} | {m['conflict_to_answer_count']} |")
    lines += ['', '选择结果：'+str(selection), '', '验证集用于选择；发布标签尚非独立语义金标准，不作为确认结果。']
    (args.run_dir/'reports/val.md').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['all','check','infer','analyze'],default='all')
    parser.add_argument('--run_dir',type=Path,default=Path('runs/qwen2.5-3b-classification-prompt-validation-v3'))
    parser.add_argument('--reference',type=Path,default=Path('runs/qwen2.5-3b-small'))
    parser.add_argument('--baseline',type=Path,default=Path('runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json'))
    parser.add_argument('--model',default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--limit_questions',type=int)
    args=parser.parse_args()
    if not args.model:parser.error('Use shell entry or pass --model')
    args.model=str(Path(args.model).resolve())
    for name in ['run_dir','reference','baseline']:setattr(args,name,e.resolve(getattr(args,name)))
    if args.run_dir==args.reference or args.run_dir==args.baseline.parents[2]:
        parser.error('Use a separate new run_dir')
    if args.limit_questions and args.run_dir.name in {'qwen2.5-3b-classification-prompt-validation-v1', 'qwen2.5-3b-classification-prompt-validation-v2', 'qwen2.5-3b-classification-prompt-validation-v3'}:
        parser.error('Smoke must have its own run_dir')
    config=e.read_json(PROMPTS)
    if config['max_new_tokens']!=8 or config['format']!='chat':raise ValueError('Unexpected decoding configuration')
    rows,source_spec=sources(args)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir/'protocol.json',protocol(args,rows,source_spec,config))
        protocol_hash=e.repro.digest_file(args.run_dir/'protocol.json')
        if args.stage in ['all','check','infer']:
            report=preflight(args,rows,tokenizer,config)
            e.repro.write_json(args.run_dir/'preflight.json',report)
            print(report,flush=True)
        if args.stage=='check':
            if not (args.run_dir/'progress.json').exists():
                e.repro.write_json(args.run_dir/'progress.json',dict(
                    status='prepared_not_started',protocol_sha256=protocol_hash,
                    candidate_order=config['candidate_order'],target_per_candidate=len(rows),
                    target_total_new=len(rows)*len(config['candidate_order']),saved_new_outputs=0,
                    launch_actor='user',resume_command='repeat the original command with the same run_dir'))
            return
        if args.stage in ['all','infer']:
            readiness=review_gate()
            e.repro.write_json(args.run_dir/'review_gate_snapshot.json',readiness)
            model=None
            try:
                for name in config['candidate_order']:
                    instruction=config['instructions'][name]
                    spec=dict(protocol_sha256=protocol_hash,candidate=name,split='val')
                    path=args.run_dir/name/'predictions.json'
                    records=cached(path,spec,rows,instruction,tokenizer)
                    if len(records)==len(rows):continue
                    if model is None:
                        assert_gpu_idle()
                        model=e.load_model(args.model)
                    for row in rows[len(records):]:
                        try:
                            records.append(generate(model,tokenizer,row,instruction))
                            e.repro.write_json(path,dict(spec=spec,records=records))
                            e.repro.write_json(args.run_dir/'progress.json',dict(status='running',candidate=name,completed_in_candidate=len(records),target_in_candidate=len(rows),last_saved_id=row['id'],protocol_sha256=protocol_hash,resume_command='repeat the original command with the same run_dir'))
                            print(f'{name} [{len(records)}/{len(rows)}] {row["id"]} -> {records[-1]["pred_mode"] or "INVALID"}',flush=True)
                        except Exception as error:
                            saved_count=len(e.read_json(path)['records']) if path.exists() else 0
                            e.repro.write_json(args.run_dir/'last_failure.json',dict(candidate=name,id=row['id'],error=str(error),saved_before_failure=saved_count))
                            raise
            finally:
                del model
            e.repro.write_json(args.run_dir/'progress.json',dict(status='generation_complete',protocol_sha256=protocol_hash,new_outputs=len(rows)*len(config['candidate_order'])))
        if args.stage in ['all','analyze']:
            analyze(args,rows,config,protocol_hash,tokenizer)
            e.repro.write_json(args.run_dir/'progress.json',dict(status='analysis_complete',protocol_sha256=protocol_hash))


if __name__=='__main__':main()
