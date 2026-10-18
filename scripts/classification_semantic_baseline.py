"""New validation-only short-label experiment; historical code stays frozen."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time

import classification_prompt_search as old

e = old.e
ROOT = e.PROJECT
PROMPTS = ROOT / 'prompts/classification_semantic_v1.json'
DEFAULT = ROOT / 'runs/qwen2.5-3b-classification-semantic-v1'
FOLLOWUP = ROOT / 'runs/qwen2.5-3b-validation-semantic-followup-2026-10-16-v1'
PILOT_MAPPING = ROOT / 'runs/qwen2.5-3b-validation-semantic-pilot-2026-10-16-v1/coordinator/mapping.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def instructions(config):
    return {'semantic_rules': config['rules'],
            'semantic_examples': config['rules'] + config['examples_suffix']}


class LabelGrammar:
    def __init__(self, tokenizer, eos_ids):
        self.eos_ids = list(eos_ids)
        require(bool(self.eos_ids), 'EOS is required')
        self.labels = {}
        for mode in e.MODES:
            tokens = tuple(tokenizer(mode, add_special_tokens=False)['input_ids'])
            require(bool(tokens) and not set(tokens) & set(self.eos_ids), 'Invalid label tokens')
            require(tokenizer.decode(tokens, skip_special_tokens=False) == mode, 'Label is not lossless')
            self.labels[tokens] = mode
        require(len(self.labels) == 3, 'Distinct label sequences required')
        for left in self.labels:
            for right in self.labels:
                require(left == right or right[:len(left)] != left, 'Labels must be prefix-free')
        self.maximum_tokens = max(map(len, self.labels)) + 1

    def allowed(self, prefix):
        prefix = tuple(prefix)
        if prefix in self.labels:
            return self.eos_ids
        allowed = sorted({seq[len(prefix)] for seq in self.labels
                          if len(seq) > len(prefix) and seq[:len(prefix)] == prefix})
        require(bool(allowed), 'Generated prefix violates label grammar')
        return allowed

    def callback(self, prompt_length):
        def allowed(batch_id, input_ids):
            return self.allowed(input_ids[prompt_length:].tolist())
        return allowed

    def verdict(self, tokens):
        if len(tokens) >= 2 and tokens[-1] in self.eos_ids:
            return self.labels.get(tuple(tokens[:-1]))
        return None


def eos_ids(model_path, tokenizer):
    value = e.read_json(Path(model_path) / 'generation_config.json').get('eos_token_id')
    value = value if value is not None else tokenizer.eos_token_id
    return value if isinstance(value, list) else [value]


def followup_reference():
    manifest = e.read_json(FOLLOWUP / 'manifest.json')
    for relative, expected in manifest['artifact_sha256'].items():
        require(e.repro.digest_file(FOLLOWUP / relative) == expected, f'Followup changed: {relative}')
    seal = e.read_json(FOLLOWUP / 'review_seal.json')
    require(seal['ratings_sha256'] == e.repro.digest_file(FOLLOWUP / 'ratings.json'), 'Followup seal mismatch')
    ratings = e.read_json(FOLLOWUP / 'ratings.json')
    mapping = e.read_json(PILOT_MAPPING)
    require(len(ratings) == 30 and len({r['pilot_id'] for r in ratings}) == 30, 'Expected explicit30 ratings')
    return {mapping[r['pilot_id']]: r for r in ratings}


def make_protocol(args, rows, source_spec, config):
    paths = [Path(__file__), PROMPTS, ROOT / 'scripts/run_classification_semantic_baseline.sh',
             ROOT / 'scripts/run_classification_semantic_baseline_review.sh',
             ROOT / 'scripts/verify_classification_semantic_baseline.py',
             ROOT / 'scripts/classification_prompt_search.py', ROOT / 'scripts/evidence_experiment.py',
             ROOT / 'scripts/small_repro.py', ROOT / 'scripts/prompt_baseline.py',
             ROOT / 'scripts/analyze_prompt_baseline.py', ROOT / 'code/prompts.py',
             ROOT / 'prompts/baseline_prompts.json', ROOT / 'configs/local.env']
    return dict(schema_version=1, task='validation_only_semantic_classification',
                model=args.model, reference=str(args.reference), baseline=str(args.baseline),
                split='val', selected_ids=[r['id'] for r in rows],
                source_spec=source_spec, configuration=config,
                code_and_prompt_sha256={str(p.relative_to(ROOT)): e.repro.digest_file(p) for p in paths},
                generation_config_sha256=e.repro.digest_file(Path(args.model) / 'generation_config.json'),
                runtime_versions={n: e.version(n) for n in ['torch', 'transformers', 'numpy']},
                legacy_validation_sha256=e.repro.digest_file(args.baseline),
                legacy_protocol_sha256=e.repro.digest_file(args.baseline.parents[2] / 'protocol.json'),
                auxiliary_reference_sha256={str(p.relative_to(ROOT)): e.repro.digest_file(p) for p in
                                           [FOLLOWUP / 'manifest.json', FOLLOWUP / 'ratings.json', PILOT_MAPPING]},
                generation=dict(dtype='bfloat16', attention='sdpa', do_sample=False, num_beams=1,
                                use_cache=True, logits_to_keep=1, max_new_tokens=8,
                                prefix_constraint='three_label_token_trie_plus_EOS'),
                parser='complete_grammar_label_and_terminal_EOS; invalid retained in denominators',
                smoke=args.limit_questions is not None,
                exposure='Prompt development used exposed val diagnosis. Reviewed30 are development examples, not independent gold. Operational unresolved-scope convention is refuse, not a claim of resolved ambiguity.',
                comparison='Old chat8 uses different instructions and unconstrained decoding. Its contrast measures combined changes, not prompt-only effects.',
                test_access='Only fixed train/val source checks and old val predictions; no test or confirmation data/predictions.',
                confirmation='No automatic confirmation launch even if screening passes.')


def parse_output(grammar, tokenizer, tokens, raw):
    mode = grammar.verdict(tokens)
    require(tokenizer.decode(tokens, skip_special_tokens=True) == raw, 'Token/text mismatch')
    return mode if mode == raw else None


def cached(path, spec, rows, instruction, tokenizer, grammar):
    if not path.exists():
        return []
    value = e.read_json(path); records = value['records']
    require(value['spec'] == spec and len(records) <= len(rows), 'Cache settings/count differ; use new run_dir')
    for row, record in zip(rows, records):
        require(all(record[k] == row[k] for k in ['id', 'original_id', 'true_mode']), 'Cached identity/order differs')
        require(record['prompt_sha256'] == e.text_hash(old.render(row, instruction, tokenizer)), 'Cached prompt differs')
        require(record['raw_output_sha256'] == e.text_hash(record['raw_output']), 'Cached text hash differs')
        tokens = record['generated_token_ids']
        require(isinstance(tokens, list) and all(type(t) is int for t in tokens)
                and 0 < len(tokens) <= 8 and len(tokens) == record['generated_tokens'], 'Cached token budget differs')
        mode = parse_output(grammar, tokenizer, tokens, record['raw_output'])
        require(record['pred_mode'] == mode and record['technical_valid'] == (mode is not None), 'Cached verdict differs')
        require(record['strict_format_pass'] == (e.legacy.parse_label(record['raw_output']) is not None), 'Cached strict parser differs')
        require(record['hit_output_limit'] == (len(tokens) == 8 and tokens[-1] not in grammar.eos_ids), 'Cached limit flag differs')
    return records


def preflight(args, rows, tokenizer, config, grammar):
    require(grammar.maximum_tokens <= config['max_new_tokens'], 'Grammar cannot complete in budget')
    context = e.read_json(Path(args.model) / 'config.json')['max_position_embeddings']
    lengths = {}
    for name, instruction in instructions(config).items():
        counts = [len(e.encode(tokenizer, old.render(r, instruction, tokenizer), 'chat')['input_ids']) for r in rows]
        require(max(counts) + 8 <= context, f'{name}: context exceeded; do not truncate evidence')
        lengths[name] = dict(instances=len(rows), max_input_tokens=max(counts),
                             mean_input_tokens=sum(counts)/len(counts), reserved_output_tokens=8)
    previous = old.baseline(args, rows, tokenizer)
    historic = sum(r['elapsed_seconds'] for r in previous)
    return dict(status='cpu_preflight_passed', candidates=lengths, context_tokens=context,
                grammar_max_tokens_including_EOS=grammar.maximum_tokens, label_token_sequences={
                    mode: list(tokens) for tokens, mode in grammar.labels.items()},
                new_outputs=len(rows)*2, historical_chat8_generation_seconds=historic,
                planning_minutes=[round(historic*2/60*1.5+2, 1), round(historic*2/60*4+6, 1)],
                note='Historical prefill/short-output timing only; new prompts/decoding not benchmarked. For smoke+full allow10-30min, add host contention. User starts GPU.',
                launch_actor='user')


def assert_gpu_idle():
    result = subprocess.run(['nvidia-smi', '-i', os.environ.get('CUDA_VISIBLE_DEVICES', '0'),
                             '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
                            capture_output=True, text=True, check=True)
    if result.stdout.strip():
        raise RuntimeError('GPU has active compute processes; retry when idle:\n' + result.stdout.strip())


def generate(model, tokenizer, row, instruction, grammar):
    import torch
    from transformers import GenerationConfig
    text = old.render(row, instruction, tokenizer)
    inputs = e.encode(tokenizer, text, 'chat', return_tensors='pt').to(model.device)
    length = inputs.input_ids.shape[1]
    require(length + 8 <= model.config.max_position_embeddings, 'Context exceeded; evidence was not truncated')
    config = GenerationConfig(max_new_tokens=8, do_sample=False, num_beams=1, use_cache=True,
                              eos_token_id=grammar.eos_ids, bos_token_id=model.generation_config.bos_token_id,
                              pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize(); start = time.monotonic()
    with torch.inference_mode():
        output = model.generate(**inputs, generation_config=config, logits_to_keep=1,
                                prefix_allowed_tokens_fn=grammar.callback(length))
    tokens = output[0, length:].tolist()
    raw = tokenizer.decode(tokens, skip_special_tokens=True)
    torch.cuda.synchronize()
    mode = parse_output(grammar, tokenizer, tokens, raw)
    return dict(id=row['id'], original_id=row['original_id'], true_mode=row['true_mode'],
                raw_output=raw, raw_output_sha256=e.text_hash(raw), generated_token_ids=tokens,
                generated_tokens=len(tokens), input_tokens=length,
                pred_mode=mode, technical_valid=mode is not None,
                strict_format_pass=e.legacy.parse_label(raw) is not None,
                hit_output_limit=len(tokens) == 8 and tokens[-1] not in grammar.eos_ids,
                elapsed_seconds=time.monotonic()-start, peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                completed_at=datetime.now(timezone.utc).isoformat(), prompt_sha256=e.text_hash(text))


def smoke_gate(rows, methods):
    require(len(rows) == 9, 'Technical smoke must have exactly9 instances per candidate')
    require(set(methods) == {'semantic_rules', 'semantic_examples'}, 'Both smoke candidates are required')
    counts = {name: sum(r['technical_valid'] and r['strict_format_pass'] and not r['hit_output_limit']
                        for r in records) for name, records in methods.items()}
    require(all(len(records) == 9 and counts[name] == 9 for name, records in methods.items()),
            f'Technical smoke failed: {counts}; full inference must not start. Preserve this run.')
    return dict(status='technical_smoke_passed', valid_per_candidate=counts,
                semantic_accuracy_gate=False, note='Grammar completion only; no semantic certification')


def load_methods(args, rows, config, protocol_hash, tokenizer, grammar):
    methods = {}
    for name, instruction in instructions(config).items():
        methods[name] = cached(args.run_dir/name/'predictions.json',
                               dict(protocol_sha256=protocol_hash, candidate=name, split='val'),
                               rows, instruction, tokenizer, grammar)
        require(len(methods[name]) == len(rows), f'{name} incomplete; resume the same launch command')
    return methods


def analyze(args, rows, config, protocol_hash, tokenizer, grammar, write=True):
    methods = load_methods(args, rows, config, protocol_hash, tokenizer, grammar)
    gate = smoke_gate(rows, methods) if args.limit_questions is not None else None
    methods = dict(legacy_chat8=old.baseline(args, rows, tokenizer), **methods)
    metrics = {}
    for name, records in methods.items():
        metrics[name] = e.classification_metrics(rows, records)
        metrics[name].update(strict_format_pass_rate=sum(r['strict_format_pass'] for r in records)/len(rows),
                             hit_output_limit_count=sum(r['hit_output_limit'] for r in records),
                             empty_output_count=sum(not r['raw_output'].strip() for r in records))
    auxiliary = followup_reference(); selected = [r for r in rows if r['id'] in auxiliary]
    aux_known = [dict(r, true_mode=auxiliary[r['id']]['semantic_mode'],
                      label=e.repro.LABEL_MAP[auxiliary[r['id']]['semantic_mode']]) for r in selected
                 if auxiliary[r['id']]['semantic_mode'] != 'unknown']
    aux_by_id = {r['id']: r for r in aux_known}
    diagnostic = dict(instances=len(selected), known=len(aux_known),
                      unknown_input_ids=[r['id'] for r in selected if auxiliary[r['id']]['semantic_mode'] == 'unknown'],
                      note='Exposed same-assistant development diagnosis, not held-out or independent gold; not used for selection.',
                      methods={name: e.classification_metrics(aux_known, [dict(r, true_mode=aux_by_id[r['id']]['true_mode'])
                                                                       for r in records if r['id'] in aux_by_id])
                               for name, records in methods.items()} if aux_known else {})
    by_method = {name: {r['id']: r['pred_mode'] or 'invalid' for r in records}
                 for name, records in methods.items()}
    diagnostic['cases'] = [dict(id=r['id'], published_mode=r['true_mode'],
                                input_mode=auxiliary[r['id']]['semantic_mode'],
                                input_confidence=auxiliary[r['id']]['confidence'],
                                predictions={name: lookup[r['id']] for name, lookup in by_method.items()})
                           for r in selected]
    selection = old.select(metrics, config) if gate is None else dict(status='smoke_only_no_selection', selected_candidate=None)
    bootstrap = {} if gate is not None else {
        f'{name}_minus_legacy_chat8': e.bootstrap_pair(rows, methods[name], methods['legacy_chat8'])
        for name in config['candidate_order']}
    if gate is None:
        bootstrap['semantic_examples_minus_semantic_rules'] = e.bootstrap_pair(rows, methods['semantic_examples'], methods['semantic_rules'])
    report = dict(split='val', instances=len(rows), methods=metrics, selection=selection,
                  paired_question_bootstrap=bootstrap, auxiliary_development_diagnosis=diagnostic,
                  technical_smoke=gate, protocol_sha256=protocol_hash,
                  note='Published-label screening, not independent semantic accuracy. Format is constrained by construction. Legacy contrast combines prompt and decoding changes. No test/confirmation inference.')
    if not write:
        return report
    e.repro.write_json(args.run_dir/'reports/val.json', report)
    lines = ['# 新语义规则分类：验证集报告', '', report['note'], '',
             '| 方法 | 发布标签Accuracy | Macro-F1 | 分类错误可答率 | 严格格式 | 不足→可答 | 冲突→可答 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, m in metrics.items():
        lines.append(f'| {name} | {m["accuracy"]:.2%} | {m["macro_f1"]:.2%} | {m["classification_false_answer_rate"]:.2%} | {m["strict_format_pass_rate"]:.2%} | {m["refuse_to_answer_count"]} | {m["conflict_to_answer_count"]} |')
    lines += ['', '筛选结果：'+str(selection), '', '## 分类型召回', '',
              '| 方法 | 充分 | 不足 | 冲突 |', '| --- | ---: | ---: | ---: |']
    for name, m in metrics.items():
        lines.append('| '+name+' | '+' | '.join(f'{m["per_class"][mode]["recall"]:.2%}' for mode in e.MODES)+' |')
    lines += ['', '## 30条开发诊断对照', '', diagnostic['note'], '',
              f'本次覆盖{len(selected)}条，确定输入{len(aux_known)}条；unknown输入单列。完整诊断计数见val.json。']
    if aux_known:
        for name, m in diagnostic['methods'].items():
            lines.append(f'- {name}：类别一致{m["correct"]}/{len(aux_known)}。')
    if selected:
        lines += ['', '| 实例 | 本轮助手判断 | 发布类别 | 旧chat8 | semantic_rules | semantic_examples |',
                  '| --- | --- | --- | --- | --- | --- |']
        for row in diagnostic['cases']:
            lines.append('| '+' | '.join([row['id'],row['input_mode'],row['published_mode']]+
                         [row['predictions'][name] for name in ['legacy_chat8']+config['candidate_order']])+' |')
    (args.run_dir/'reports/val.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    if gate is not None:
        e.repro.write_json(args.run_dir/'smoke_gate.json', gate)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'check', 'infer', 'analyze'], default='all')
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    parser.add_argument('--reference', type=Path, default=ROOT/'runs/qwen2.5-3b-small')
    parser.add_argument('--baseline', type=Path, default=ROOT/'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json')
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--limit_questions', type=int, choices=[3])
    args = parser.parse_args()
    if not args.model:
        parser.error('Use the shell entry or pass --model')
    args.model = str(Path(args.model).resolve())
    for key in ['run_dir', 'reference', 'baseline']:
        setattr(args, key, e.resolve(getattr(args, key)))
    require(args.run_dir != args.reference and args.run_dir != args.baseline.parents[2], 'Use a new run_dir')
    require(args.limit_questions is None or args.run_dir != DEFAULT, 'Smoke needs a separate directory')
    config = e.read_json(PROMPTS)
    require(config['candidate_order'] == ['semantic_rules', 'semantic_examples'] and config['max_new_tokens'] == 8, 'Unexpected protocol settings')
    rows, source_spec = old.sources(args)
    reference = followup_reference()
    require(set(reference) <= {r['id'] for r in e.repro.load_rows(args.reference/'data/instances_val.jsonl')}, 'Auxiliary IDs outside val')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    grammar = LabelGrammar(tokenizer, eos_ids(args.model, tokenizer))
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir/'protocol.json', make_protocol(args, rows, source_spec, config))
        protocol_hash = e.repro.digest_file(args.run_dir/'protocol.json')
        if args.stage in ['all', 'check', 'infer']:
            report = preflight(args, rows, tokenizer, config, grammar)
            e.repro.write_json(args.run_dir/'preflight.json', report)
            print(report, flush=True)
        if args.stage == 'check':
            if not (args.run_dir/'progress.json').exists():
                e.repro.write_json(args.run_dir/'progress.json', dict(status='prepared_not_started',
                    target_per_candidate=len(rows), target_total_new=len(rows)*2, saved_new_outputs=0,
                    protocol_sha256=protocol_hash, launch_actor='user'))
            return
        if args.stage in ['all', 'infer']:
            model = None
            candidate = instance = None
            try:
                for candidate, instruction in instructions(config).items():
                    path = args.run_dir/candidate/'predictions.json'
                    spec = dict(protocol_sha256=protocol_hash, candidate=candidate, split='val')
                    records = cached(path, spec, rows, instruction, tokenizer, grammar)
                    if len(records) == len(rows):
                        continue
                    if model is None:
                        assert_gpu_idle(); model = e.load_model(args.model)
                    for row in rows[len(records):]:
                        instance = row['id']
                        records.append(generate(model, tokenizer, row, instruction, grammar))
                        e.repro.write_json(path, dict(spec=spec, records=records))
                        e.repro.write_json(args.run_dir/'progress.json', dict(status='running', candidate=candidate,
                            completed_in_candidate=len(records), target_per_candidate=len(rows), last_saved_id=instance,
                            protocol_sha256=protocol_hash, launch_actor='user'))
                        print(f'{candidate} [{len(records)}/{len(rows)}] {instance} -> {records[-1]["pred_mode"] or "INVALID"}', flush=True)
            except Exception as error:
                e.repro.write_json(args.run_dir/'last_failure.json', dict(candidate=candidate, id=instance, error=str(error)))
                raise
            finally:
                del model
            e.repro.write_json(args.run_dir/'progress.json', dict(status='generation_complete', new_outputs=len(rows)*2,
                                                                protocol_sha256=protocol_hash))
        if args.stage in ['all', 'analyze']:
            report = analyze(args, rows, config, protocol_hash, tokenizer, grammar)
            e.repro.write_json(args.run_dir/'progress.json', dict(status='analysis_complete',
                protocol_sha256=protocol_hash, new_outputs=len(rows)*2, selection=report['selection']))
            print('Analysis complete: '+str(report['selection']), flush=True)


if __name__ == '__main__':
    main()
