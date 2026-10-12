"""Read-only independent counts and durable snapshot of a completed grid run."""

import csv
import datetime
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import classification_grid as grid

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/qwen2.5-3b-classification-grid'
REFERENCE = ROOT / 'runs/qwen2.5-3b-small'
MODES = ['answer', 'refuse', 'conflict']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label(text):
    match = re.fullmatch(r'(answer|refuse|conflict)[.!]?', text.strip(), re.I)
    return match.group(1).lower() if match else None


def main():
    protocol = read(RUN / 'protocol.json')
    protocol_hash = sha(RUN / 'protocol.json')
    for name, expected in protocol['code_sha256'].items():
        path = ROOT / ('code' if name == 'prompts.py' else 'scripts') / name
        assert sha(path) == expected, f'Frozen code changed: {name}'
    audit = read(RUN / 'audit.json')
    assert audit['confirmation_questions'] == 380 and audit['confirmation_instances'] == 1140
    reserved = set(audit['unseen_confirmation_original_ids'])
    legacy = read(ROOT / 'runs/qwen2.5-3b-prompt-baseline/predictions.json')
    legacy_lookup = {r['id']: r for r in legacy['records']}
    snapshots, all_records, counts = {}, {}, {}
    artifacts = {str(p.relative_to(ROOT)): sha(p) for p in [RUN / 'protocol.json', RUN / 'audit.json', RUN / 'preflight.json']}
    generated_times = []
    for split, n in [('val', 285), ('test', 300)]:
        rows = [json.loads(s) for s in (REFERENCE / f'data/instances_{split}.jsonl').read_text().splitlines()]
        assert len(rows) == n
        assert not ({r['original_id'] for r in rows} & reserved)
        report_path = RUN / f'reports/{split}.json'
        report = read(report_path)
        assert report['protocol_sha256'] == protocol_hash
        assert report['n_instances'] == n and len(report['paired_question_bootstrap']) == 8
        snapshots[split] = report
        records_by_method = {'router': grid.reference_router(REFERENCE, rows, split)}
        for condition, (fmt, budget) in grid.CONDITIONS.items():
            path = RUN / condition / split / 'predictions.json'
            saved = read(path)
            records = saved['records']
            assert len(records) == n and len({r['id'] for r in records}) == n
            assert saved['spec']['protocol_sha256'] == protocol_hash
            assert saved['spec']['condition'] == condition and saved['spec']['split'] == split
            assert saved['spec']['max_new_tokens'] == budget
            if condition == 'plain8' and split == 'test':
                assert saved['spec']['legacy_source_sha256'] == sha(ROOT / 'runs/qwen2.5-3b-prompt-baseline/predictions.json')
            for row, record in zip(rows, records):
                assert record['id'] == row['id'] and record['true_mode'] == row['true_mode']
                first = next((s.strip() for s in record['raw_output'].splitlines() if s.strip()), '')
                assert record['pred_mode'] == label(first)
                assert record['strict_format_pass'] == (label(record['raw_output']) is not None)
                assert 0 <= record['generated_tokens'] <= budget
                if condition == 'plain8' and split == 'test':
                    assert record['reused_legacy'] is True
                    assert record['raw_output'] == legacy_lookup[row['id']]['raw_output']
                else:
                    generated_times.append(record['completed_at'])
            records_by_method[condition] = records
            counts[f'{condition}/{split}'] = n
            artifacts[str(path.relative_to(ROOT))] = sha(path)
        for method, records in records_by_method.items():
            matrix = [[0]*4 for _ in MODES]
            for row, record in zip(rows, records):
                pred = record['pred_mode']
                matrix[MODES.index(row['true_mode'])][MODES.index(pred) if pred in MODES else 3] += 1
            metric = report['methods'][method]
            assert metric['confusion_matrix'] == matrix
            correct = sum(matrix[i][i] for i in range(3))
            assert metric['correct'] == correct
            f1s = []
            for i, mode in enumerate(MODES):
                support, predicted, tp = sum(matrix[i]), sum(r[i] for r in matrix), matrix[i][i]
                f1 = 2*tp/(support+predicted) if support+predicted else 0
                f1s.append(f1)
                for field, value in [('support', support), ('correct', tp), ('f1', f1),
                                     ('recall', tp/support), ('precision', tp/predicted if predicted else 0)]:
                    assert abs(metric['per_class'][mode][field]-value) < 1e-12, (split, method, mode, field)
            assert abs(metric['accuracy']-correct/n) < 1e-12
            assert abs(metric['macro_f1']-sum(f1s)/3) < 1e-12
            assert metric['refuse_to_answer_count'] == matrix[1][0]
            assert metric['conflict_to_answer_count'] == matrix[2][0]
            far = (matrix[1][0]+matrix[2][0])/(sum(matrix[1])+sum(matrix[2]))
            assert abs(metric['classification_false_answer_rate']-far) < 1e-12
            if method != 'router':
                assert abs(metric['parse_coverage']-(n-sum(r[3] for r in matrix))/n) < 1e-12
                assert metric['strict_format_pass_count'] == sum(r['strict_format_pass'] for r in records)
                assert metric['hit_output_limit_count'] == sum(r['hit_output_limit'] for r in records)
                assert metric['empty_output_count'] == sum(not r['raw_output'].strip() for r in records)
        for name, paired in report['paired_question_bootstrap'].items():
            left, right = name.split('_minus_')
            assert paired['resamples'] == 10000 and paired['seed'] == 42
            for field, values in paired['differences'].items():
                if field.endswith('_recall'):
                    mode = field[:-len('_recall')]
                    delta = report['methods'][left]['per_class'][mode]['recall'] - report['methods'][right]['per_class'][mode]['recall']
                else:
                    delta = report['methods'][left][field] - report['methods'][right][field]
                assert abs(values['estimate']-delta) < 1e-12, (split, name, field)
                assert values['95ci'][0] <= values['95ci'][1]
        all_records[split] = records_by_method
        artifacts[str(report_path.relative_to(ROOT))] = sha(report_path)
    assert sum(counts.values()) == 2340 and len(generated_times) == 2040
    # No tuning: these describe the four predeclared conditions on validation.
    val = snapshots['val']['methods']
    val_best = {
        field: [c for c in grid.CONDITIONS if val[c][field] == max(val[x][field] for x in grid.CONDITIONS)]
        for field in ['accuracy', 'macro_f1']
    }
    quality_path = ROOT / 'docs/records/2026-10-11-free-answer-followup-audit-conflict-quality.csv'
    quality = {r['id']: r['quality'] for r in csv.DictReader(quality_path.open())}
    flagged = list(csv.DictReader((ROOT / 'docs/records/2026-10-11-free-answer-followup-audit-editing-metadata.csv').open()))
    strata = {}
    budget_agreement = {}
    router_net_correct = {}
    for split, methods in all_records.items():
        budget_agreement[split] = {}
        for fmt in ['plain', 'chat']:
            short, long = methods[fmt+'8'], methods[fmt+'64']
            budget_agreement[split][fmt] = dict(
                n=len(short), identical_first_line_predictions=sum(a['pred_mode'] == b['pred_mode'] for a, b in zip(short, long)),
                short_raw_text_is_prefix_of_long=sum(b['raw_output'].startswith(a['raw_output']) for a, b in zip(short, long)))
        router_net_correct[split] = {}
        for condition in grid.CONDITIONS:
            router_net_correct[split][condition] = {
                mode: snapshots[split]['methods']['router']['per_class'][mode]['correct'] - snapshots[split]['methods'][condition]['per_class'][mode]['correct']
                for mode in MODES}
    for method, records in all_records['test'].items():
        strata[method] = {}
        for group in sorted(set(quality.values())):
            rr = [r for r in records if quality.get(r['id']) == group]
            strata[method][group] = dict(n=len(rr), predicted=dict(Counter(r['pred_mode'] or 'invalid' for r in rr)))
        flagged_ids = {r['id'] for r in flagged if r['split'] == 'test'}
        for marked in [True, False]:
            rr = [r for r in records if r['true_mode'] == 'conflict' and (r['id'] in flagged_ids) == marked]
            strata[method]['explicit_editing_metadata' if marked else 'no_matched_editing_metadata'] = dict(
                n=len(rr), predicted=dict(Counter(r['pred_mode'] or 'invalid' for r in rr)))
    snapshot = dict(recorded_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                    status='verified_complete', execution_actor='assistant', model=protocol['model'],
                    frozen_protocol=protocol, protocol_sha256=protocol_hash, counts=counts,
                    new_inferences=2040, reused_legacy_inferences=300,
                    new_generation_first_at=min(generated_times), new_generation_last_at=max(generated_times),
                    reports=snapshots, validation_best_descriptive=val_best,
                    within_format_budget_agreement=budget_agreement,
                    router_minus_condition_correct_by_class=router_net_correct,
                    quality_strata_predictions=strata, artifact_sha256=artifacts,
                    checks=dict(metric_summaries_recounted=10, parser_outputs_checked=2340,
                                paired_difference_points_checked=128,
                                raw_legacy_outputs_unchanged=300, frozen_code_hashes=len(protocol['code_sha256']),
                                reserved_confirmation_questions=380, reserved_overlap=0),
                    limitations=['diagnostic previously inspected test subset', 'legacy plain8/test post-hoc parsing',
                                 'router validation calibration-in-sample', 'classification FAR is not free-answer behavior',
                                 'quality/metadata strata are post-hoc diagnostic'])
    destination = ROOT / 'docs/records/2026-10-11-classification-grid-verified.json'
    destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n')
    print(destination.relative_to(ROOT))
    print('Verified all 2,340 parsed outputs, 300 reused raw outputs, 10 metric summaries and frozen code hashes.')
    print('Validation best:', val_best)
    for method, m in snapshots['test']['methods'].items():
        print(method, dict(accuracy=m['accuracy'], macro_f1=m['macro_f1'],
                           FAR=m['classification_false_answer_rate'], refuse_to_answer=m['refuse_to_answer_count'],
                           conflict_to_answer=m['conflict_to_answer_count']))


if __name__ == '__main__':
    main()
