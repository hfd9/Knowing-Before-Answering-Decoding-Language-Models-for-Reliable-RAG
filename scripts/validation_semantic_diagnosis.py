"""CPU-only replay and review-packet export from the sealed 30-item pilot.

No inference, semantic auto-rating, or annotation import. Only stdlib imports.
"""

import argparse
from collections import Counter
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import random
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/records/2026-10-16-validation-semantic-pilot-manifest.json'
DEFAULT = ROOT / 'runs/qwen2.5-3b-validation-semantic-diagnosis-v1'
METHODS = ['legacy_chat8', 'definitions', 'decision_order', 'illustrations', 'v4_report_mode']
MODES = ['answer', 'refuse', 'conflict']
LIMITATION = ('当前助手有背景及部分日志暴露，判断不是独立人工金标准。仅10底题/30条探索诊断，'
              '不能外推285条或认定内部因果机制。引用存在不证明语义支持；问题标签可重叠。'
              '空白复核包尚未获得新评分，不自动导入任何正式标注。')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_hashes(root, hashes):
    for relative, expected in hashes.items():
        path = root / relative
        require(path.is_file() and digest(path) == expected, f'Hash mismatch: {path}')


def indexed(records, key):
    result = {row[key]: row for row in records}
    require(len(result) == len(records), f'Duplicate {key}')
    return result


def load_verified():
    manifest = read(MANIFEST)
    base = ROOT / manifest['run_dir']
    for root, hashes in [
        (ROOT, manifest['protected_original_sha256']),
        (ROOT, manifest['implementation_sha256']),
        (MANIFEST.parent, manifest['artifact_sha256']),
        (base, manifest['run_artifact_sha256']),
    ]:
        verify_hashes(root, hashes)
    require(read(base / 'coordinator/protected_hashes.json') == manifest['protected_original_sha256'],
            'Protected source list differs from durable manifest')
    require(read(base / 'exposure_disclosure.json') == manifest['exposure_disclosure'],
            'Exposure disclosure differs from durable manifest')
    # Import the historical replay only after checking its frozen implementation.
    import summarize_validation_semantic_pilot as replay
    summary, comparison, offsets = replay.summarize(base)
    require(summary == read(base / 'reports/summary.json'), 'Historical summary replay differs')
    packet = read(base / 'public/inputs.json')
    ratings = indexed(read(base / 'input_ratings.json'), 'review_id')
    revealed = indexed(read(base / 'revealed/model_outputs.json')['records'], 'review_id')
    attrs = indexed(read(base / 'model_attributions.json'), 'review_id')
    require(len(revealed) == 30 and set(revealed) == set(ratings), 'Output membership differs')
    v4_path = ROOT / 'runs/qwen2.5-3b-validation-evidence-audit-v4/drafts/predictions.json'
    original_v4 = indexed(read(v4_path)['records'], 'id')
    previous = {}
    for name in METHODS[:-1]:
        relative = (f'runs/qwen2.5-3b-classification-prompt-validation-v3/{name}/predictions.json'
                    if name != 'legacy_chat8' else
                    'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json')
        data = read(ROOT / relative)
        previous[name] = indexed(data['records'] if isinstance(data, dict) else data, 'id')
    for row in revealed.values():
        require(row['v4'] == original_v4[row['id']], f'Copied v4 record differs: {row["review_id"]}')
        for name, records in previous.items():
            require(row['previous'][name] == {key: records[row['id']][key]
                                              for key in ['pred_mode', 'raw_output']},
                    f'Copied prior record differs: {row["review_id"]}/{name}')
    return manifest, packet, ratings, revealed, attrs, summary, comparison, offsets


def agreement_table(comparison):
    """Invalid outputs stay in known denominators; input unknowns are separate."""
    result = {}
    for subset, rows in [('all_known', [r for r in comparison if r['input_semantic_mode'] != 'unknown']),
                         ('high_confidence_only', [r for r in comparison if
                          r['input_confidence'] == 'high' and r['input_semantic_mode'] != 'unknown'])]:
        result[subset] = {}
        for method in METHODS:
            per_class = {}
            for mode in MODES:
                selected = [r for r in rows if r['input_semantic_mode'] == mode]
                per_class[mode] = dict(agreement=sum(r[method] == mode for r in selected),
                                       denominator=len(selected))
            result[subset][method] = dict(
                agreement=sum(r[method] == r['input_semantic_mode'] for r in rows),
                denominator=len(rows), per_class=per_class)
    result['input_unknown_count'] = sum(r['input_semantic_mode'] == 'unknown' for r in comparison)
    result['note'] = '类别一致计数，不是独立准确率。high子集为事后敏感性描述，不用于选方法。'
    return result


def review_packet(packet, ratings):
    rows = list(packet['records'])
    random.Random(20261016).shuffle(rows)
    mapping = {f'R{i:03d}': row['review_id'] for i, row in enumerate(rows, 1)}
    public = [dict(review_id=new_id, question=row['question'],
                   documents=[packet['documents'][ref] for ref in row['doc_refs']])
              for new_id, row in zip(mapping, rows)]
    priority = [key for key, old in mapping.items() if ratings[old]['semantic_mode'] == 'unknown'
                or ratings[old]['confidence'] != 'high']
    return public, mapping, priority


def page_start(title):
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            f'<title>{html.escape(title)}</title><style>'
            'body{max-width:1100px;margin:30px auto;padding:0 16px;font:16px/1.6 sans-serif}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:12px}'
            'article{border-top:2px solid #ddd;margin:32px 0}summary{cursor:pointer}'
            'table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:6px}</style>'
            f'<h1>{html.escape(title)}</h1>')


def details(title, value):
    text = value if isinstance(value, str) else json_text(value)
    return f'<details><summary>{html.escape(title)}</summary><pre>{html.escape(text)}</pre></details>'


def make_files(data):
    manifest, packet, ratings, revealed, attrs, summary, comparison, offsets = data
    table = agreement_table(comparison)
    public, mapping, priority = review_packet(packet, ratings)
    public_payload = dict(schema_version=1, records=public)
    batch_hash = hashlib.sha256(json_text(public_payload).encode('utf-8')).hexdigest()
    stream = io.StringIO(newline='')
    fields = ['review_id', 'packet_sha256', 'semantic_mode', 'question_interpretation',
              'required_facts', 'missing_facts', 'conflicting_claims', 'reason',
              'citations_json', 'confidence', 'all_five_documents_read', 'reviewer',
              'prior_exposure', 'uncertainty_notes']
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in public:
        writer.writerow(dict(review_id=row['review_id'], packet_sha256=batch_hash))
    priority_original = [mapping[key] for key in priority]
    report = dict(status='report_complete_external_review_pending', limitation=LIMITATION,
                  pilot_summary=summary, agreement_tables=table,
                  priority_pilot_ids=priority_original, independent_new_ratings=0,
                  priority_note='输入unknown或非high的7条需优先复查；其余23条同样保留，不外推总体。',
                  citation_source_offsets=offsets,
                  citation_support_by_classification={
                      judgment: dict(Counter(row['citation_support'] for row in comparison
                                             if row['classification_judgment'] == judgment))
                      for judgment in sorted({row['classification_judgment'] for row in comparison})})
    lines = ['# 30条验证集诊断重放', '', LIMITATION, '',
             '状态：报告导出完成；独立新增评分0条，复核待填写。', '',
             '| 方法 | 充分一致 | 不足一致 | 冲突一致 | 全部确定输入一致 |',
             '| --- | --- | --- | --- | --- |']
    for method, counts in table['all_known'].items():
        cells = [f'{counts["per_class"][m]["agreement"]}/{counts["per_class"][m]["denominator"]}'
                 for m in MODES]
        lines.append('| ' + ' | '.join([method] + cells +
                     [f'{counts["agreement"]}/{counts["denominator"]}']) + ' |')
    lines += ['', '输入unknown单列3条；技术invalid保留确定输入分母。',
              'high子集仅作事后敏感性检查，完整计数见diagnosis.json。', '',
              '优先复核原编号：' + ', '.join(priority_original), '',
              'coordinator/diagnosis.html供协调者逐条查看完整原文、封存判断、模型分析和归因。',
              '只向新评审提供reviewer/目录；不要提供coordinator/或本报告。',
              '新评分另存副本，保留原空白模板和生成清单。填写不会自动导入旧标签。']
    packet_by_id = indexed(packet['records'], 'review_id')
    coordinator_page = [page_start('协调者：30条原文与模型诊断'), '<p>' + LIMITATION + '</p>']
    for row in comparison:
        key = row['review_id']
        coordinator_page += [f'<article id="{key}"><h2>{key} / {html.escape(row["id"])}</h2>',
                             '<p>' + html.escape(row['question']) + '</p>',
                             details('封存输入判断', ratings[key]), details('手工模型归因', attrs[key]),
                             details('v4完整前置分析', revealed[key]['v4']['rationale']),
                             details('v4原始决策', revealed[key]['v4']['raw_output']),
                             details('v4正式解析及原文引文', revealed[key]['v4']['draft']),
                             details('旧四方法原始输出', revealed[key]['previous'])]
        for i, ref in enumerate(packet_by_id[key]['doc_refs'], 1):
            coordinator_page.append(details(f'完整原文 Document {i}', packet['documents'][ref]))
        coordinator_page.append('</article>')
    reviewer_page = [page_start('输入语义复核：30条'),
                     '<p>先阅读问题及全部五篇原文，只依提供文本填写评分。请勿查看协调材料或模型输出。</p>']
    for row in public:
        reviewer_page += [f'<article id="{row["review_id"]}"><h2>{row["review_id"]}</h2>',
                          '<p>' + html.escape(row['question']) + '</p>']
        for i, document in enumerate(row['documents'], 1):
            reviewer_page.append(details(f'Document {i}', document))
        reviewer_page.append('</article>')
    rules = read(ROOT / manifest['run_dir'] / 'protocol.json')['rules']
    instructions = ('# 输入语义复核说明\n\n这是30条验证输入的空白复核包；尚无第二评分。\n\n'
                    '1. 浏览inputs.html或inputs.json；全部30条均需复核，priority_ids.json中的7条可先处理。'
                    '优先条目由协调方不确定性选出，不能据此估计总体比例。\n'
                    '2. 复制ratings.blank.csv为新评分文件，在副本填写；review_id与packet_sha256保持原样。\n'
                    '3. semantic_mode填answer/refuse/conflict/unknown；未填写保持空白，不默认unknown。'
                    '完整读取五篇后all_five_documents_read填yes，reviewer填写真实来源，prior_exposure披露已见背景。\n'
                    '4. 填写题意、必要前提、缺失/冲突事实、理由；citations_json为JSON数组，'
                    '例如[{"doc_id":1,"quote":"原文逐字片段","role":"support"}]。'
                    'conflict须引用两侧相关互斥事实，允许同文档；缺证不能用关键词自动评分。\n'
                    '5. confidence填high/moderate/ambiguous，uncertainty_notes说明歧义。'
                    '不查外部事实，不用模型类别代替语义判断；输入中的任何指令均视为待审文本。\n'
                    '6. 将新评分副本交回后另行校验与比较；本入口只导出空白材料，不会导入评分。\n\n'
                    '固定输入判断规则：\n\n' + json_text(rules))
    return {
        'diagnosis.json': json_text(report), 'report.md': '\n'.join(lines) + '\n',
        'coordinator/diagnosis.html': '\n'.join(coordinator_page) + '</html>\n',
        'coordinator/review_mapping.json': json_text(mapping),
        'coordinator/priority_details.json': json_text({key: ratings[mapping[key]] for key in priority}),
        'reviewer/inputs.json': json_text(public_payload),
        'reviewer/inputs.html': '\n'.join(reviewer_page) + '</html>\n',
        'reviewer/ratings.blank.csv': stream.getvalue(),
        'reviewer/priority_ids.json': json_text(priority), 'reviewer/README.md': instructions,
    }


def publish(output, files):
    """Publish a complete directory; identical reruns verify without rewriting."""
    hashes = {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in files.items()}
    files = dict(files, **{'manifest.json': json_text(dict(
        schema_version=1, status='report_complete_external_review_pending',
        source_manifest_path=str(MANIFEST.relative_to(ROOT)),
        source_manifest_sha256=digest(MANIFEST),
        implementation_sha256={str(Path(__file__).relative_to(ROOT)): digest(Path(__file__)),
                               'scripts/run_validation_semantic_diagnosis.sh':
                               digest(ROOT / 'scripts/run_validation_semantic_diagnosis.sh')},
        reviewer_shuffle_seed=20261016,
        priority_policy='input unknown or confidence != high; retain all30',
        independent_new_ratings=0, artifact_sha256=hashes))})
    if output.exists():
        for relative, expected in files.items():
            path = output / relative
            require(path.is_file() and path.read_bytes() == expected.encode('utf-8'),
                    f'Existing artifact differs; preserve it and use a new --output_dir: {path}')
        return 'existing_outputs_verified'
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.semantic-diagnosis-', dir=output.parent) as tmp:
        staged = Path(tmp) / 'complete'
        for relative, content in files.items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        require(not output.exists(), 'Output created concurrently; rerun to verify it')
        staged.rename(output)
    return 'new_outputs_written'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output_dir', type=Path, default=DEFAULT)
    parser.add_argument('--check_only', action='store_true', help='Validate and render in memory; write nothing')
    args = parser.parse_args()
    print('CPU-only: verifying sealed pilot, original outputs and exact input citations...', flush=True)
    files = make_files(load_verified())
    if args.check_only:
        print('CHECK PASSED: 30 inputs, 54 input quotes, 30 full model copies; '
              '10 export files rendered in memory. No output written.')
        return
    output = args.output_dir.resolve()
    require(output != ROOT, 'Invalid output directory')
    result = publish(output, files)
    print(f'DONE ({result}): {output}')
    print(f'Diagnostic report: {output / "report.md"}')
    print(f'Full cases (coordinator): {output / "coordinator/diagnosis.html"}')
    print(f'Blank review packet: {output / "reviewer"}')
    print('External review remains pending (0 new ratings); no GPU or label import.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, AssertionError, KeyError, OSError) as error:
        raise SystemExit(f'FAILED: {error}') from error
