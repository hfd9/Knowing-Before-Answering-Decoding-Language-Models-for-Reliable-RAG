"""Matched free-answer prompts, retrained probes and blinded behavior review."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import pickle
import time

import numpy as np

import evidence_experiment as e
import free_answer_review as review


def feature_shape(model):
    config = e.read_json(Path(model) / 'config.json')
    return [config['num_hidden_layers'], config['hidden_size']]


def checkpoint_spec(protocol_hash, fmt, split, stage):
    return {'protocol_sha256': protocol_hash, 'format': fmt, 'split': split,
            'stage': stage, 'feature_convention': e.FEATURE_CONVENTION}


def save_feature(directory, index, h):
    path = directory / 'features' / f'{index:05d}.npy'
    e.save_array(path, h)
    return {'feature_file': str(path.relative_to(directory)), 'feature_sha256': e.repro.digest_file(path)}


def feature_records(args, rows, fmt, split, protocol_hash, tokenizer):
    path = args.run_dir / fmt / split / 'states.json'
    spec = checkpoint_spec(protocol_hash, fmt, split, 'extract')
    records = e.load_records(path, spec, rows, 'free_answer', fmt, tokenizer, feature_shape(args.model))
    return path, spec, records


def extract(args, all_rows, protocol_hash, tokenizer):
    import torch
    model = None
    try:
        for fmt in args.formats:
            for split in ['train', 'val']:
                rows = all_rows[split]
                path, spec, records = feature_records(args, rows, fmt, split, protocol_hash, tokenizer)
                if len(records) == len(rows):
                    print(f'{fmt}/{split}: states complete; skip', flush=True)
                    continue
                if model is None:
                    model = e.load_model(args.model)
                for row in rows[len(records):]:
                    text = e.render_input(row, 'free_answer', fmt, tokenizer)
                    inputs = e.encode(tokenizer, text, fmt, return_tensors='pt').to(model.device)
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.synchronize()
                    start = time.monotonic()
                    try:
                        with e.LastPromptCapture(model) as capture, torch.inference_mode():
                            model.model(**inputs, use_cache=False, output_hidden_states=False)
                        h = capture.array()
                        torch.cuda.synchronize()
                        record = {'id': row['id'], 'original_id': row['original_id'], 'true_mode': row['true_mode'],
                                  'prompt_sha256': e.text_hash(text), 'input_tokens': inputs.input_ids.shape[1],
                                  'elapsed_seconds': time.monotonic() - start,
                                  'peak_allocated_gib': torch.cuda.max_memory_allocated() / 2**30,
                                  'completed_at': datetime.now(timezone.utc).isoformat(),
                                  **save_feature(path.parent, len(records), h)}
                        records.append(record)
                        e.repro.write_json(path, {'spec': spec, 'records': records})
                        print(f"{fmt}/{split} states [{len(records)}/{len(rows)}] {row['id']}", flush=True)
                    except Exception as error:
                        e.repro.write_json(args.run_dir / 'last_failure.json', {'stage': 'extract', 'format': fmt, 'split': split, 'id': row['id'], 'error': str(error)})
                        raise RuntimeError(f"State extraction failed: {fmt}/{split}/{row['id']}; resume the same command") from error
                    finally:
                        del inputs
    finally:
        del model
        torch.cuda.empty_cache()


def train_probes(args, all_rows, protocol_hash, tokenizer):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    for fmt in args.formats:
        features, labels, source = {}, {}, {}
        for split in ['train', 'val']:
            path, _, records = feature_records(args, all_rows[split], fmt, split, protocol_hash, tokenizer)
            if len(records) != len(all_rows[split]):
                raise ValueError(f'Incomplete {fmt}/{split} extraction')
            features[split] = np.stack([np.load(path.parent / r['feature_file'], allow_pickle=False) for r in records])
            labels[split] = np.array([r['label'] for r in all_rows[split]])
            source[split] = e.repro.digest_file(path)
        directory = args.run_dir / fmt / 'probe'
        spec = {'protocol_sha256': protocol_hash, 'format': fmt, 'source_states_sha256': source,
                'C': 1.0, 'solver': 'lbfgs', 'max_iter': 2000, 'selection': 'validation accuracy, first maximum',
                'scaler_fit_split': 'train', 'calibration': 'sigmoid', 'calibration_split': 'val'}
        if (directory / 'probe.json').exists():
            metadata = e.read_json(directory / 'probe.json')
            if metadata['spec'] != spec or metadata['pickle_sha256'] != e.repro.digest_file(directory / 'probe.pkl'):
                raise ValueError(f'{fmt}: probe fingerprint mismatch; use a new run directory')
            print(f'{fmt}: matching trained probe exists; skip', flush=True)
            continue
        best, sweep = None, {}
        for layer in range(features['train'].shape[1]):
            scaler = StandardScaler()
            train = scaler.fit_transform(features['train'][:, layer].astype(np.float32))
            val = scaler.transform(features['val'][:, layer].astype(np.float32))
            classifier = LogisticRegression(C=1.0, solver='lbfgs', max_iter=2000, random_state=42)
            classifier.fit(train, labels['train'])
            prediction = classifier.predict(val)
            records = [{'id': row['id'], 'true_mode': row['true_mode'], 'pred_mode': e.MODES[int(p)]}
                       for row, p in zip(all_rows['val'], prediction)]
            metrics = e.classification_metrics(all_rows['val'], records)
            sweep[str(layer)] = metrics
            if best is None or metrics['accuracy'] > best['validation_accuracy']:
                best = {'layer': layer, 'scaler': scaler, 'classifier': classifier,
                        'validation_accuracy': metrics['accuracy']}
            print(f"{fmt} L{layer:02d}: val accuracy={metrics['accuracy']:.4f}", flush=True)
        calibrated = CalibratedClassifierCV(best['classifier'], cv='prefit', method='sigmoid')
        calibrated.fit(best['scaler'].transform(features['val'][:, best['layer']].astype(np.float32)), labels['val'])
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / 'probe.pkl.tmp'
        with tmp.open('wb') as f:
            pickle.dump({'layer': best['layer'], 'scaler': best['scaler'], 'router': calibrated, 'spec': spec}, f)
        tmp.replace(directory / 'probe.pkl')
        e.repro.write_json(directory / 'probe.json', {'spec': spec, 'selected_layer_zero_based': best['layer'],
                           'validation_selection_accuracy': best['validation_accuracy'], 'layer_sweep': sweep,
                           'pickle_sha256': e.repro.digest_file(directory / 'probe.pkl')})


def load_probe(args, fmt, protocol_hash):
    directory = args.run_dir / fmt / 'probe'
    metadata = e.read_json(directory / 'probe.json')
    if metadata['spec']['protocol_sha256'] != protocol_hash or metadata['pickle_sha256'] != e.repro.digest_file(directory / 'probe.pkl'):
        raise ValueError(f'{fmt}: probe integrity mismatch')
    for split in ['train', 'val']:
        if metadata['spec']['source_states_sha256'][split] != e.repro.digest_file(args.run_dir / fmt / split / 'states.json'):
            raise ValueError(f'{fmt}/{split}: probe training states changed')
    with (directory / 'probe.pkl').open('rb') as f:
        probe = pickle.load(f)
    if probe['spec'] != metadata['spec']:
        raise ValueError(f'{fmt}: probe specification mismatch')
    return probe, metadata['pickle_sha256']


def generation_records(args, rows, fmt, protocol_hash, tokenizer):
    probe, fingerprint = load_probe(args, fmt, protocol_hash)
    path = args.run_dir / fmt / 'test' / 'predictions.json'
    spec = dict(checkpoint_spec(protocol_hash, fmt, 'test', 'generate'),
                probe_sha256=fingerprint, max_new_tokens=128)
    records = e.load_records(path, spec, rows, 'free_answer', fmt, tokenizer, feature_shape(args.model))
    for record in records:
        h = np.load(path.parent / record['feature_file'], allow_pickle=False)
        probability = probe['router'].predict_proba(probe['scaler'].transform(h[probe['layer']][None].astype(np.float32)))[0]
        expected = e.MODES[int(probe['router'].classes_[int(np.argmax(probability))])]
        stored = [record['probe_probabilities'][e.MODES[int(c)]] for c in probe['router'].classes_]
        if (not record['probe_decision_pre_first_token'] or record['probe_pred'] != expected or
                record['probe_layer_zero_based'] != probe['layer'] or not np.allclose(stored, probability, atol=1e-8)):
            raise ValueError(f"{record['id']}: saved pre-generation probe result mismatch")
    return path, spec, records, probe


def generate(args, rows, protocol_hash, tokenizer):
    import torch
    model = None
    try:
        for fmt in args.formats:
            path, spec, records, probe = generation_records(args, rows, fmt, protocol_hash, tokenizer)
            if len(records) == len(rows):
                print(f'{fmt}/test: generations complete; skip', flush=True)
                continue
            if model is None:
                model = e.load_model(args.model)
            for row in rows[len(records):]:
                decision = {}

                def before_first_token(h):
                    x = probe['scaler'].transform(h[probe['layer']][None].astype(np.float32))
                    probability = probe['router'].predict_proba(x)[0]
                    classes = probe['router'].classes_
                    decision.update(probe_pred=e.MODES[int(classes[int(np.argmax(probability))])],
                                    probe_probabilities={e.MODES[int(c)]: float(p) for c, p in zip(classes, probability)},
                                    probe_layer_zero_based=probe['layer'], probe_decision_pre_first_token=True)
                try:
                    record, h = e.generate_one(model, tokenizer, row, 'free_answer', fmt, 128,
                                               on_prefill=before_first_token, capture=True)
                    if not decision:
                        raise ValueError('Probe decision was not made in prefill')
                    record.update(decision)
                    record.update(save_feature(path.parent, len(records), h))
                    records.append(record)
                    e.repro.write_json(path, {'spec': spec, 'records': records})
                    print(f"{fmt}/test [{len(records)}/{len(rows)}] {row['id']} pre-probe={record['probe_pred']}", flush=True)
                except Exception as error:
                    e.repro.write_json(args.run_dir / 'last_failure.json', {'stage': 'generate', 'format': fmt, 'id': row['id'], 'error': str(error)})
                    raise RuntimeError(f"Generation failed: {fmt}/{row['id']}; resume the same command") from error
    finally:
        del model
        torch.cuda.empty_cache()


def analyze(args, rows, protocol_hash, tokenizer):
    outputs = {}
    for fmt in args.formats:
        _, _, records, _ = generation_records(args, rows, fmt, protocol_hash, tokenizer)
        if len(records) != len(rows):
            raise ValueError(f'{fmt}: incomplete free-answer generation')
        outputs[fmt] = records
    manifest = review.export_review(args.run_dir, {r['id']: r for r in rows}, outputs)
    annotations = review.load_annotations(args.annotations, manifest, e.repro.digest_file(args.run_dir / 'review/manifest.json'))
    report = {'protocol_sha256': protocol_hash, 'n_instances_per_format': len(rows),
              'annotation_file': str(args.annotations), 'rubric': review.RUBRIC,
              'formats': {}, 'probe_behavior_feed_back': False,
              'claim_limit': 'Associations between pre-generation decodability and behavior; not causal proof of knowing or ignoring evidence.'}
    annotated_records = []
    probes_by_format = {}
    joined_by_format = {}
    for fmt, records in outputs.items():
        joined = [dict(record, behavior=dict(annotations.get((fmt, record['id']), {}))) for record in records]
        probe_records = [dict(r, pred_mode=r['probe_pred']) for r in records]
        probes_by_format[fmt] = probe_records
        joined_by_format[fmt] = joined
        metrics = e.classification_metrics(rows, probe_records)
        behavior = review.behavior_summary(joined)
        pending = sum(any(r['behavior'].get(field) is None for field in review.FIELDS) for r in joined)
        report['formats'][fmt] = {'probe_classification': metrics, 'behavior': behavior,
                                 'review_items_with_unknown_fields': pending,
                                 'hit_output_limit_count': sum(r['hit_output_limit'] for r in records),
                                 'review_status': 'complete' if not pending else 'pending_or_ambiguous',
                                 'probe_sha256': e.repro.digest_file(args.run_dir / fmt / 'probe/probe.pkl')}
        annotated_records.extend(dict(r, format=fmt) for r in joined)
    if set(outputs) == {'plain', 'chat'}:
        report['probe_paired_chat_minus_plain'] = e.bootstrap_pair(rows, probes_by_format['chat'], probes_by_format['plain'])
        paired = {}
        for mode, field in [('refuse', 'has_substantive_answer'), ('conflict', 'selects_single_answer')]:
            left = [r for r in joined_by_format['chat'] if r['true_mode'] == mode]
            right = [r for r in joined_by_format['plain'] if r['true_mode'] == mode]
            if all(r['behavior'].get(field) is not None for r in left + right):
                delta = np.array([int(a['behavior'][field]) - int(b['behavior'][field]) for a, b in zip(left, right)])
                rng = np.random.default_rng(42)
                means = np.concatenate([rng.choice(delta, size=(500, len(delta)), replace=True).mean(axis=1) for _ in range(20)])
                paired[f'{mode}_{field}_chat_minus_plain'] = {'estimate': float(delta.mean()),
                    'question_bootstrap_95ci': np.quantile(means, [0.025, 0.975]).tolist(), 'resamples': 10000, 'seed': 42}
        report['paired_behavior_differences'] = paired
    output = args.run_dir / 'reports'
    e.repro.write_json(output / 'behavior.json', report)
    e.repro.write_json(output / 'joined_records.json', annotated_records)
    lines = ['# 自由回答：前生成信号与实际行为', '',
             '探针在首次 prefill 内做出判断，结果未反馈给生成器。各输入格式使用独立、同模板训练的探针。',
             '行为由盲审标注；未知项保留在分母并报告上下界。生成完成不等于行为评估已完成。', '',
             '| 格式 | 指标 | 已确认分子 | 完整分母 | 未知 | 比例 / 范围 |', '| --- | --- | ---: | ---: | ---: | --- |']
    for fmt, summary in report['formats'].items():
        for name, m in summary['behavior']['rates'].items():
            if m['rate'] is not None:
                value = f"{m['rate']:.2%}"
            elif m['denominator']:
                value = f"待审核 / [{m['lower_bound']:.2%}, {m['upper_bound']:.2%}]"
            else:
                value = '无分母'
            lines.append(f"| {fmt} | {name} | {m['known_positive']} | {m['denominator']} | {m['unknown']} | {value} |")
    lines += ['', '打开 review/blind_review.html 进行盲审，导出 annotations.csv 到本实验根目录，再运行 --stage analyze。',
              '先使用当前已查看测试集诊断；保留测试底题上的确认须在设置冻结后另行执行。']
    (output / 'behavior.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"Behavior report: {output / 'behavior.md'}", flush=True)
    print(f"Blind review: {args.run_dir / 'review/blind_review.html'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'check', 'extract', 'probe', 'generate', 'analyze'], default='all')
    parser.add_argument('--run_dir', type=Path, default=Path('runs/qwen2.5-3b-free-answer-study'))
    parser.add_argument('--reference_run', type=Path, default=Path('runs/qwen2.5-3b-small'))
    parser.add_argument('--model', default=os.environ.get('KBA_MODEL'))
    parser.add_argument('--formats', nargs='+', choices=['plain', 'chat'], default=['plain', 'chat'])
    parser.add_argument('--limit_questions', type=int)
    parser.add_argument('--annotations', type=Path)
    args = parser.parse_args()
    if not args.model:
        parser.error('Use run_free_answer_study.sh or pass --model')
    args.run_dir, args.reference_run = e.resolve(args.run_dir), e.resolve(args.reference_run)
    args.model = str(Path(args.model).resolve())
    args.annotations = e.resolve(args.annotations) if args.annotations else args.run_dir / 'annotations.csv'
    if args.run_dir == args.reference_run:
        parser.error('Use a separate free-answer run directory')
    if len(set(args.formats)) != len(args.formats):
        parser.error('Duplicate input formats')
    rows, specs = e.load_reference(args.reference_run, args.model, args.limit_questions)
    protocol = e.make_protocol(args.reference_run, args.model, rows, specs, __file__, 'free_answer_study')
    protocol.update(max_new_tokens=128, formats=['plain', 'chat'], feature_convention=e.FEATURE_CONVENTION,
                    probe={'C': 1.0, 'solver': 'lbfgs', 'max_iter': 2000, 'selection': 'validation accuracy',
                           'scaler_fit_split': 'train', 'calibration': 'sigmoid', 'calibration_split': 'val'},
                    behavior_rubric=review.RUBRIC)
    with e.legacy.run_lock(args.run_dir):
        e.freeze(args.run_dir / 'protocol.json', protocol)
        protocol_hash = e.repro.digest_file(args.run_dir / 'protocol.json')
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
        if args.stage in ['all', 'check', 'extract', 'generate']:
            result = e.check_lengths(args.model, rows, tokenizer, 'free_answer', args.formats, [128])
            e.repro.write_json(args.run_dir / 'preflight.json', result)
            print(result, flush=True)
        if args.stage == 'check':
            return
        if args.stage in ['all', 'extract']:
            extract(args, rows, protocol_hash, tokenizer)
        if args.stage in ['all', 'probe']:
            train_probes(args, rows, protocol_hash, tokenizer)
        if args.stage in ['all', 'generate']:
            generate(args, rows['test'], protocol_hash, tokenizer)
        if args.stage in ['all', 'analyze']:
            analyze(args, rows['test'], protocol_hash, tokenizer)


if __name__ == '__main__':
    main()
