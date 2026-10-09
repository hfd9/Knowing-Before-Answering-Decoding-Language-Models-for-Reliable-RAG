"""Matched plain/chat x 8/64-token classification experiment and reliability audit."""

import argparse
import csv
import os
from pathlib import Path
import pickle

import numpy as np

import evidence_experiment as e

CONDITIONS = {'plain8': ('plain', 8), 'plain64': ('plain', 64), 'chat8': ('chat', 8), 'chat64': ('chat', 64)}


def legacy_records(path, reference, model, rows):
    saved = e.read_json(path)
    old = saved['spec']
    full_rows = e.repro.load_rows(reference / 'data/instances_test.jsonl')
    expected = e.repro.feature_spec(argparse.Namespace(model=model, template='P0'), full_rows,
                                  reference / 'data/instances_test.jsonl')
    if old['model_and_source'] != expected or old['instruction'] != e.legacy.INSTRUCTION:
        raise ValueError('Legacy plain8 model/data/instruction mismatch')
    if old['generation'] != {'max_new_tokens': 8, 'do_sample': False, 'num_beams': 1, 'dtype': 'bfloat16',
                              'attention': 'sdpa', 'chat_wrapper': False, 'logits_to_keep': 1}:
        raise ValueError('Legacy plain8 decoding mismatch')
    checked = e.legacy.load_checkpoint(path.parent, old, full_rows)
    if len(checked) != len(full_rows):
        raise ValueError('Legacy plain8 experiment is incomplete')
    lookup = {r['id']: r for r in checked}
    return [dict(lookup[r['id']], pred_mode=e.first_line_label(lookup[r['id']]['raw_output']),
                 strict_format_pass=e.legacy.parse_label(lookup[r['id']]['raw_output']) is not None,
                 reused_legacy=True) for r in rows]


def reference_router(reference, rows, split):
    if split == 'test':
        all_rows = e.repro.load_rows(reference / 'data/instances_test.jsonl')
        saved = e.read_json(reference / 'results/router_test_predictions.json')
        e.classification_metrics(all_rows, saved)
        lookup = {r['id']: r for r in saved}
        return [lookup[r['id']] for r in rows]
    # Validation predictions are calibration-in-sample, and labeled as such in reports.
    with (reference / 'results/router_hidden_dev.pkl').open('rb') as f:
        probe = pickle.load(f)
    if probe['layers'] != [e.read_json(reference / 'results/router_metrics.json')['selected_layer']]:
        raise ValueError('Saved router layer mismatch')
    all_rows = e.repro.load_rows(reference / 'data/instances_val.jsonl')
    h = np.load(reference / 'activations/H_P0_val.npy', mmap_mode='r')
    prediction = probe['router'].predict(probe['scaler'].transform(h[:, probe['layers'][0]].astype(np.float32)))
    lookup = {r['id']: {'id': r['id'], 'true_mode': r['true_mode'], 'pred_mode': e.MODES[int(p)]}
              for r, p in zip(all_rows, prediction)}
    return [lookup[r['id']] for r in rows]


def condition_spec(protocol_hash, condition, split, legacy_path):
    fmt, budget = CONDITIONS[condition]
    return {'protocol_sha256': protocol_hash, 'condition': condition, 'split': split,
            'format': fmt, 'max_new_tokens': budget,
            'legacy_source_sha256': e.repro.digest_file(legacy_path) if condition == 'plain8' and split == 'test' else None,
            'first_line_policy_fixed_before_new_inference': True,
            'legacy_test_first_line_policy_was_posthoc': condition == 'plain8' and split == 'test'}


def analyze(args, rows_by_split, protocol_hash, tokenizer):
    for split in args.splits:
        rows = rows_by_split[split]
        methods = {'router': reference_router(args.reference_run, rows, split)}
        summaries = {'router': e.classification_metrics(rows, methods['router'])}
        for condition in args.conditions:
            fmt, _ = CONDITIONS[condition]
            path = args.run_dir / condition / split / 'predictions.json'
            records = e.load_records(path, condition_spec(protocol_hash, condition, split, args.legacy_predictions),
                                     rows, 'classification', fmt, tokenizer)
            if len(records) != len(rows):
                raise ValueError(f"Incomplete {condition}/{split}: {len(records)}/{len(rows)}; resume inference")
            methods[condition] = records
            metrics = e.classification_metrics(rows, records)
            metrics.update(strict_format_pass_count=sum(r['strict_format_pass'] for r in records),
                           strict_format_pass_rate=sum(r['strict_format_pass'] for r in records) / len(rows),
                           hit_output_limit_count=sum(r['hit_output_limit'] for r in records),
                           empty_output_count=sum(not r['raw_output'].strip() for r in records),
                           inference_seconds_sum=sum(r['elapsed_seconds'] for r in records),
                           legacy_posthoc_parsing=condition == 'plain8' and split == 'test')
            summaries[condition] = metrics
        pairs = [(name, 'router') for name in args.conditions]
        pairs += [('plain64', 'plain8'), ('chat64', 'chat8'), ('chat8', 'plain8'), ('chat64', 'plain64')]
        paired = {}
        for left, right in pairs:
            if left in methods and right in methods:
                paired[f'{left}_minus_{right}'] = e.bootstrap_pair(rows, methods[left], methods[right])
        report = {'split': split, 'n_instances': len(rows), 'n_questions': len(rows) // 3,
                  'methods': summaries, 'paired_question_bootstrap': paired,
                  'metric_note': 'classification_false_answer_rate is not a generated-answer behavior rate',
                  'validation_router_note': 'Original router calibration used validation labels; its validation predictions are calibration-in-sample.',
                  'test_role': 'previously inspected diagnostic subset', 'protocol_sha256': protocol_hash}
        output = args.run_dir / 'reports'
        e.repro.write_json(output / f'{split}.json', report)
        lines = [f'# 四条件分类对照：{split}', '',
                 f'底题：{len(rows)//3}；实例：{len(rows)}。invalid 保留在指标分母中。', '',
                 '| 方法 | Accuracy | Macro-F1 | 错误可答判定率 | 严格格式 | 首行可解析 | Refuse→Answer | Conflict→Answer |',
                 '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for name, m in summaries.items():
            strict = f"{m['strict_format_pass_rate']:.2%}" if name != 'router' else '不适用'
            parsed = f"{m['parse_coverage']:.2%}" if name != 'router' else '不适用'
            lines.append(f"| {name} | {m['accuracy']:.2%} | {m['macro_f1']:.2%} | {m['classification_false_answer_rate']:.2%} | {strict} | {parsed} | {m['refuse_to_answer_count']} | {m['conflict_to_answer_count']} |")
        lines += ['', '错误可答判定率评价三分类决策，不是生成器的缺证回答率。',
                  'plain8/test 复用历史原始输出，其首行解析是事后补充分析；新条件的解析规则在推理前固定。',
                  '当前 test 已查看，属于诊断集。val 路由器结果使用了已在该集合校准的模型。']
        per_class = []
        for name, m in summaries.items():
            lines += ['', f'## {name}', '', '| 类别 | Precision | Recall | F1 | Support |', '| --- | ---: | ---: | ---: | ---: |']
            for mode, values in m['per_class'].items():
                per_class.append({'method': name, 'class': mode, **values})
                lines.append(f"| {mode} | {values['precision']:.2%} | {values['recall']:.2%} | {values['f1']:.2%} | {values['support']} |")
            lines += ['', '| 真实 / 预测 | answer | refuse | conflict | invalid |', '| --- | ---: | ---: | ---: | ---: |']
            for mode, counts in zip(e.MODES, m['confusion_matrix']):
                lines.append(f'| {mode} | ' + ' | '.join(map(str, counts)) + ' |')
        (output / f'{split}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with (output / f'{split}_per_class.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(per_class[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(per_class)
        errors = []
        for index, row in enumerate(rows):
            predictions = {name: records[index]['pred_mode'] for name, records in methods.items()}
            if any(pred != row['true_mode'] for pred in predictions.values()):
                errors.append({'id': row['id'], 'original_id': row['original_id'], 'question': row['question'],
                               'true_mode': row['true_mode'], 'predictions': predictions})
        e.repro.write_json(output / f'{split}_errors.json', errors)
        print(f"Report: {output / (split + '.md')}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'check', 'audit', 'infer', 'analyze'], default='all')
    parser.add_argument('--run_dir', type=Path, default=Path('runs/qwen2.5-3b-classification-grid'))
    parser.add_argument('--reference_run', type=Path, default=Path('runs/qwen2.5-3b-small'))
    parser.add_argument('--legacy_predictions', type=Path, default=Path('runs/qwen2.5-3b-prompt-baseline/predictions.json'))
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--splits', nargs='+', choices=['val', 'test'], default=['val', 'test'])
    parser.add_argument('--conditions', nargs='+', choices=list(CONDITIONS), default=list(CONDITIONS))
    parser.add_argument('--limit_questions', type=int)
    args = parser.parse_args()
    if not args.model:
        parser.error('Use run_classification_grid.sh or pass --model')
    for name in ['run_dir', 'reference_run', 'legacy_predictions']:
        setattr(args, name, e.resolve(getattr(args, name)))
    args.model = str(Path(args.model).resolve())
    if args.run_dir == args.reference_run or args.run_dir == args.legacy_predictions.parent:
        parser.error('Use a new grid directory, separate from all reference experiments')
    if len(set(args.conditions)) != len(args.conditions) or len(set(args.splits)) != len(args.splits):
        parser.error('Duplicate conditions/splits')
    rows, specs = e.load_reference(args.reference_run, args.model, args.limit_questions)
    protocol = e.make_protocol(args.reference_run, args.model, rows, specs, __file__, 'classification_grid')
    protocol['conditions'] = {name: {'format': fmt, 'max_new_tokens': budget} for name, (fmt, budget) in CONDITIONS.items()}
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir / 'protocol.json', protocol)
        protocol_hash = e.repro.digest_file(args.run_dir / 'protocol.json')
        if args.stage in ['all', 'check', 'audit']:
            audit = e.audit_reference(args.reference_run, args.model)
            e.repro.write_json(args.run_dir / 'audit.json', audit)
            print('Audit passed; confirmation IDs reserved, no confirmation inference.', flush=True)
        if args.stage == 'audit':
            return
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
        if args.stage in ['all', 'check', 'infer']:
            report = e.check_lengths(args.model, {s: rows[s] for s in args.splits}, tokenizer,
                                     'classification', ['plain', 'chat'], [8, 64])
            e.repro.write_json(args.run_dir / 'preflight.json', report)
            print(report, flush=True)
        if args.stage == 'check':
            return
        if args.stage in ['all', 'infer']:
            model = None
            try:
                for split in args.splits:
                    for condition in args.conditions:
                        fmt, budget = CONDITIONS[condition]
                        spec = condition_spec(protocol_hash, condition, split, args.legacy_predictions)
                        path = args.run_dir / condition / split / 'predictions.json'
                        records = e.load_records(path, spec, rows[split], 'classification', fmt, tokenizer)
                        if not records and condition == 'plain8' and split == 'test':
                            records = legacy_records(args.legacy_predictions, args.reference_run, args.model, rows[split])
                            e.repro.write_json(path, {'spec': spec, 'records': records})
                            print(f'Reused {len(records)} historical plain8/test outputs.', flush=True)
                        if len(records) == len(rows[split]):
                            print(f'{condition}/{split}: complete; skip', flush=True)
                            continue
                        if model is None:
                            model = e.load_model(args.model)
                        for row in rows[split][len(records):]:
                            try:
                                record, _ = e.generate_one(model, tokenizer, row, 'classification', fmt, budget)
                                records.append(record)
                                e.repro.write_json(path, {'spec': spec, 'records': records})
                                print(f"{condition}/{split} [{len(records)}/{len(rows[split])}] {row['id']} -> {record['pred_mode'] or 'INVALID'}", flush=True)
                            except Exception as error:
                                e.repro.write_json(args.run_dir / 'last_failure.json', {'condition': condition, 'split': split, 'id': row['id'], 'error': str(error)})
                                raise RuntimeError(f"Failed {condition}/{split}/{row['id']}; resume the same command") from error
            finally:
                del model
        if args.stage in ['all', 'analyze']:
            analyze(args, rows, protocol_hash, tokenizer)


if __name__ == '__main__':
    main()
