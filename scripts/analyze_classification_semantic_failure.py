"""CPU post-analysis of verified val outputs; reuse explicit ratings without relabeling.

This module is separate from frozen inference dependencies. It performs independent
counts and records observable disagreements, not inferred model reasoning.
"""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODES = ('answer', 'refuse', 'conflict')
PREDICTED = MODES + ('invalid',)
METHODS = ('legacy_chat8', 'semantic_rules', 'semantic_examples')
FORMAL = Path('runs/qwen2.5-3b-classification-semantic-v1')
SMOKE = Path('runs/qwen2.5-3b-classification-semantic-smoke-v1')
DEFAULT = Path('runs/qwen2.5-3b-classification-semantic-postanalysis-2026-10-18-v2')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def index(values, field='id'):
    result = {value[field]: value for value in values}
    require(len(result) == len(values), f'Duplicate {field}')
    return result


def counts(rows, predictions):
    """Count invalid in accuracy/FN denominators; FAR uses non-answer inputs."""
    require(bool(rows), 'Empty evaluation set')
    require(set(predictions) == {r['id'] for r in rows}, 'Prediction IDs differ')
    matrix = [[0] * 4 for _ in MODES]
    for row in rows:
        require(row['true_mode'] in MODES, 'Unknown inputs must be excluded explicitly')
        predicted = predictions[row['id']] or 'invalid'
        require(predicted in PREDICTED, 'Unsupported prediction')
        matrix[MODES.index(row['true_mode'])][PREDICTED.index(predicted)] += 1
    per_class = {}
    for i, mode in enumerate(MODES):
        support = sum(matrix[i])
        tp = matrix[i][i]
        predicted = sum(row[i] for row in matrix)
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * tp / (support + predicted) if support + predicted else 0.0
        per_class[mode] = dict(support=support, correct=tp, precision=precision, recall=recall, f1=f1)
    correct = sum(matrix[i][i] for i in range(3))
    nonanswer = sum(matrix[1]) + sum(matrix[2])
    return dict(n_instances=len(rows), correct=correct, accuracy=correct / len(rows),
                macro_f1=sum(c['f1'] for c in per_class.values()) / 3,
                classification_false_answer_rate=(matrix[1][0] + matrix[2][0]) / nonanswer if nonanswer else None,
                refuse_to_answer_count=matrix[1][0], conflict_to_answer_count=matrix[2][0],
                confusion_matrix=matrix, per_class=per_class,
                predicted_counts={p: sum(row[i] for row in matrix) for i, p in enumerate(PREDICTED)})


def compare(rows, left, right):
    require(set(left) == set(right) == {r['id'] for r in rows}, 'Paired ID mismatch')
    groups = {key: [] for key in ('improved', 'regressed', 'both_correct', 'both_wrong')}
    transitions = {m: [[0] * 4 for _ in PREDICTED] for m in MODES}
    for row in rows:
        key = row['id']
        lp, rp = left[key] or 'invalid', right[key] or 'invalid'
        lc, rc = lp == row['true_mode'], rp == row['true_mode']
        group = 'both_correct' if lc and rc else 'improved' if lc else 'regressed' if rc else 'both_wrong'
        groups[group].append(key)
        transitions[row['true_mode']][PREDICTED.index(rp)][PREDICTED.index(lp)] += 1
    return dict(direction='left minus right', groups=groups,
                group_counts={k: len(v) for k, v in groups.items()},
                net_correct=len(groups['improved']) - len(groups['regressed']),
                transition_rows='right prediction', transition_columns='left prediction',
                prediction_order=list(PREDICTED), transitions_by_published_class=transitions)


def check_metrics(actual, saved):
    for name in ('n_instances', 'correct', 'confusion_matrix', 'refuse_to_answer_count', 'conflict_to_answer_count'):
        require(actual[name] == saved[name], f'Independent {name} differs')
    for name in ('accuracy', 'macro_f1', 'classification_false_answer_rate'):
        require(math.isclose(actual[name], saved[name], rel_tol=1e-12, abs_tol=1e-12), f'{name} differs')
    for mode in MODES:
        for name, value in actual['per_class'][mode].items():
            require(math.isclose(value, saved['per_class'][mode][name], rel_tol=1e-12, abs_tol=1e-12),
                    f'{mode}/{name} differs')


def build(root):
    source = Path('runs/qwen2.5-3b-small/data/instances_val.jsonl')
    rating_path = Path('docs/records/2026-10-16-validation-semantic-followup-ratings.json')
    mapping_path = Path('runs/qwen2.5-3b-validation-semantic-pilot-2026-10-16-v1/coordinator/mapping.json')
    paths = [source, rating_path, mapping_path, FORMAL/'protocol.json', FORMAL/'reports/val.json',
             SMOKE/'protocol.json', SMOKE/'reports/val.json',
             Path('docs/records/2026-10-18-classification-semantic-baseline-full-replay.json'),
             Path('docs/records/2026-10-18-classification-semantic-baseline-smoke-replay.json')]
    prediction_paths = dict(legacy_chat8=Path('runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json'),
                            **{name: FORMAL/name/'predictions.json' for name in METHODS[1:]})
    paths += list(prediction_paths.values())
    paths += [SMOKE/name/'predictions.json' for name in METHODS[1:]]
    before = {str(p): digest(root/p) for p in paths}
    report = read(root/FORMAL/'reports/val.json')
    for base, replay_path in ((FORMAL, paths[7]), (SMOKE, paths[8])):
        replay = read(root/replay_path)
        require(replay['status'] == 'verified_complete' and replay['published_metrics_and_bootstrap_replayed'],
                'Complete frozen verifier must pass first')
        require(replay['protocol_sha256'] == digest(root/base/'protocol.json'), 'Replay protocol differs')
    rows = [json.loads(line) for line in (root/source).read_text().splitlines()]
    require(len(rows) == 285 and len(index(rows)) == 285, 'Expected fixed val285')
    require(len({r['original_id'] for r in rows}) == 95, 'Expected95 base questions')
    by_id = index(rows)
    predictions = {}
    generation = {}
    for name, path in prediction_paths.items():
        values = read(root/path)['records']
        require(len(values) == 285 and set(index(values)) == set(by_id), 'Incomplete or duplicate outputs')
        predictions[name] = {r['id']: r['pred_mode'] for r in values}
        generation[name] = dict(seconds=sum(r['elapsed_seconds'] for r in values),
                                last_completed=max(r['completed_at'] for r in values),
                                max_peak_allocated_gib=max(r['peak_allocated_gib'] for r in values))
    metrics = {name: counts(rows, pred) for name, pred in predictions.items()}
    for name, actual in metrics.items():
        check_metrics(actual, report['methods'][name])
    pairs = [('semantic_rules', 'legacy_chat8'), ('semantic_examples', 'legacy_chat8'),
             ('semantic_examples', 'semantic_rules')]
    paired = {f'{left}_minus_{right}': compare(rows, predictions[left], predictions[right]) for left, right in pairs}
    ratings = read(root/rating_path)
    mapping = read(root/mapping_path)
    require(len(ratings) == 30 and len(index(ratings, 'pilot_id')) == 30, 'Expected explicit30 ratings')
    cases = []
    citation_count = 0
    for rating in sorted(ratings, key=lambda r: r['pilot_id']):
        key = mapping[rating['pilot_id']]
        row = by_id[key]
        supports = []
        for citation in rating['citations']:
            doc = row['docs'][citation['doc_id']-1]
            start = doc.find(citation['quote'])
            require(start >= 0, f'Citation source differs: {key}')
            supports.append(dict(citation, start=start, end=start+len(citation['quote'])))
            citation_count += 1
        truth = rating['semantic_mode']
        require(truth in MODES + ('unknown',), 'Invalid explicit rating')
        cases.append(dict(id=key, pilot_id=rating['pilot_id'], question=row['question'],
                          published_mode=row['true_mode'], input_mode=truth, confidence=rating['confidence'],
                          predictions={n: p[key] for n, p in predictions.items()},
                          observations={n: 'input_unknown_excluded' if truth == 'unknown' else
                                        'class_agreement' if p[key] == truth else
                                        f'input_{truth}_predicted_{p[key] or "invalid"}'
                                        for n, p in predictions.items()},
                          interpretation=rating['question_interpretation'], input_reason=rating['reason'],
                          required_facts=rating['required_facts'], missing_facts=rating['missing_facts'],
                          conflicting_claims=rating['conflicting_claims'],
                          answer_if_supported=rating['answer_if_supported'],
                          uncertainty_notes=rating['uncertainty_notes'], citations=supports,
                          judgment_source=str(rating_path),
                          judgment_status='Reuse exposed same-assistant development rating; no new semantic score.'))
    known = [dict(by_id[c['id']], true_mode=c['input_mode']) for c in cases if c['input_mode'] != 'unknown']
    require(len(known) == 29 and citation_count == 50, 'Expected29 known /50 existing citations')
    development_metrics = {name: counts(known, {r['id']: pred[r['id']] for r in known})
                           for name, pred in predictions.items()}
    for name, actual in development_metrics.items():
        check_metrics(actual, report['auxiliary_development_diagnosis']['methods'][name])
    require(before == {str(p): digest(root/p) for p in paths}, 'Read-only source changed during analysis')
    return dict(status='verified_postanalysis', source_sha256=before,
                population=dict(published_instances=285, base_questions=95, development_instances=30,
                                development_known=29, development_unknown=1),
                prediction_order=list(PREDICTED), published_metrics=metrics, generation=generation,
                published_paired_changes=paired,
                paired_question_bootstrap=report['paired_question_bootstrap'],
                selection=report['selection'], development_metrics=development_metrics,
                development_prediction_counts={n: dict(Counter(p[c['id']] for c in cases))
                                               for n, p in predictions.items()},
                development_cases=cases, existing_citations_checked=citation_count,
                limitation='Published-label metrics; exposed same-assistant development judgments reused, not independent gold. Label-only outputs do not reveal internal reasoning. No new semantic labels, GPU, test/confirmation inference or changes to frozen sources.')


def csv_text(cases):
    stream = io.StringIO(newline='')
    fields = ['id', 'pilot_id', 'published_mode', 'input_mode', 'confidence'] + list(METHODS) + [
        'rules_observation', 'examples_observation', 'input_reason', 'uncertainty_notes', 'citation_count']
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for c in cases:
        writer.writerow({k: c[k] for k in fields[:5]} | c['predictions'] | dict(
            rules_observation=c['observations']['semantic_rules'],
            examples_observation=c['observations']['semantic_examples'],
            input_reason=c['input_reason'], uncertainty_notes=c['uncertainty_notes'], citation_count=len(c['citations'])))
    return stream.getvalue()


def markdown(summary):
    lines = ['# 新语义分类：独立计数与30条开发诊断对照', '', summary['limitation'], '',
             '输入判断逐字复用10月16日追加评分；本轮仅验证50条引文来源并对齐新标签，没有新增语义评分。', '',
             '| 方法 | 发布类别正确 | Macro-F1 | answer/refuse/conflict输出数 |', '| --- | ---: | ---: | --- |']
    for name, m in summary['published_metrics'].items():
        lines.append(f'| {name} | {m["correct"]}/285 | {m["macro_f1"]:.2%} | '+
                     '/'.join(str(m['predicted_counts'][x]) for x in MODES)+' |')
    lines += ['', '| 对照（左减右） | 由错变对 | 由对变错 | 净正确条数 |', '| --- | ---: | ---: | ---: |']
    for name, pair in summary['published_paired_changes'].items():
        lines.append(f'| {name} | {pair["group_counts"]["improved"]} | {pair["group_counts"]["regressed"]} | {pair["net_correct"]} |')
    lines += ['', '| 方法 | 充分一致 | 不足一致 | 冲突一致 | 合计 |', '| --- | ---: | ---: | ---: | ---: |']
    for name, m in summary['development_metrics'].items():
        lines.append('| '+name+' | '+' | '.join(f'{m["per_class"][x]["correct"]}/{m["per_class"][x]["support"]}' for x in MODES)+f' | {m["correct"]}/29 |')
    for c in summary['development_cases']:
        lines += ['', f'## {c["pilot_id"]} / {c["id"]}', '', c['question'], '',
                  f'原发布类别：{c["published_mode"]}；已有输入判断：{c["input_mode"]}（{c["confidence"]}）。', '',
                  '预测：'+ '；'.join(f'{n}={p}' for n, p in c['predictions'].items())+'。', '',
                  '可观察对照：'+ '；'.join(f'{n}: {c["observations"][n]}' for n in METHODS[1:])+'。', '',
                  '复用输入判断理由：'+c['input_reason'], '', '保留条件：'+c['uncertainty_notes']]
        for cite in c['citations']:
            lines += ['', f'- 文档{cite["doc_id"]}字符[{cite["start"]},{cite["end"]})：{cite["quote"]}']
    return '\n'.join(lines)+'\n'


def write_new(path, content):
    if path.exists():
        require(path.read_bytes() == content.encode('utf-8'), f'Refuse to overwrite: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8', newline='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    args = parser.parse_args()
    base = args.run_dir if args.run_dir.is_absolute() else ROOT/args.run_dir
    require(base.resolve().is_relative_to((ROOT/'runs').resolve()), 'Use a separate run under runs/')
    require(base.resolve() not in [(ROOT/FORMAL).resolve(), (ROOT/SMOKE).resolve()], 'Preserve frozen experiment')
    summary = build(ROOT)
    summary['analysis_script_sha256'] = digest(Path(__file__))
    artifacts = dict(summary_json=json.dumps(summary, ensure_ascii=False, indent=2)+'\n',
                     cases_csv=csv_text(summary['development_cases']), report_md=markdown(summary))
    filenames = dict(summary_json='summary.json', cases_csv='cases.csv', report_md='report.md')
    for key, content in artifacts.items():
        write_new(base/filenames[key], content)
    manifest = dict(status=summary['status'], source_sha256=summary['source_sha256'],
                    analysis_script_sha256=summary['analysis_script_sha256'],
                    artifact_sha256={name: digest(base/name) for name in filenames.values()})
    write_new(base/'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status=summary['status'], run_dir=str(base),
                         population=summary['population'], selection=summary['selection'],
                         source_files_unchanged=len(summary['source_sha256']), citations_checked=50), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
