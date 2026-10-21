"""Replay hand-authored, post-hoc descriptions of 23 existing answers; stdlib/CPU only."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'docs/records/2026-10-21-insufficient-answer-audit'
RUN = 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1'
BEHAVIOR = 'docs/records/2026-10-21-semantic-transfer-exploratory-behavior'
MANUAL = PREFIX + '-manual.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def file_sha(path):
    return sha_bytes((ROOT / path).read_bytes())


def quote(text, snippet, document_index=None, endpoint=None):
    start = text.find(snippet)
    require(start >= 0 and text.count(snippet) == 1, 'Quote missing or ambiguous: ' + snippet)
    result = dict(start=start, end=start + len(snippet), quote=snippet,
                  text_sha256=sha_bytes(text.encode()))
    if document_index is not None:
        result.update(document_index=document_index, endpoint=endpoint)
    return result


def compute():
    old_paths = read('docs/records/2026-10-21-semantic-transfer-exploratory-retrain-preserved.json')
    seal = read('docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json')
    require(len(old_paths) == 901, 'Wrong source preservation inventory')
    for path, expected in {**old_paths, **seal['files']}.items():
        require(file_sha(path) == expected, 'Sealed source changed: ' + path)
    require(seal['fit_attempts'] == 1 and seal['remaining_original_design_fits'] == 0,
            'Fit budget changed')
    rows = list(csv.DictReader((ROOT / (BEHAVIOR + '-cells.csv')).open()))
    require(len(rows) == len({r['id'] for r in rows}) == 240, 'Wrong original behavior table')
    insufficient = [r for r in rows if r['exposed_author_input_mode'] == 'refuse']
    selected = [r for r in insufficient if r['has_substantive_answer'] == 'yes']
    require(len(insufficient) == 60 and len(selected) == 23, 'Selection differs from sealed result')
    manual = read(MANUAL)
    require(manual['history_exposed'] is True and manual['independent_gold'] is False
            and manual['approved_for_training'] is False, 'Wrong provenance')
    judgments = {c['id']: c for c in manual['cases']}
    require(len(judgments) == len(manual['cases']) == 23
            and set(judgments) == {r['id'] for r in selected}, 'Hand audit selection mismatch')
    packet_path = RUN + '/behavior_review/packet.json'
    packet = read(packet_path)
    items = {r['item_id']: r for r in packet['items']}
    mapping_path = RUN + '/coordinator/behavior_mapping.json'
    mapping = read(mapping_path)
    predictions_path = RUN + '/predictions.json'
    predictions = {r['id']: r for r in read(predictions_path)['records']}
    old_ratings = {r['item_id']: r for r in read(BEHAVIOR + '-ratings.json')['ratings']}
    require(len(items) == len(mapping) == len(predictions) == 240, 'Source join size mismatch')
    require(set(mapping.values()) == set(items), 'Mapping is not bijective')
    require(all(v is None for v in read(RUN + '/approved_labels.json').values()),
            'Formal labels changed')
    cases, inventory, displayed = [], [], {}
    for row in selected:
        key = row['id']
        require(row['condition'] == 'I', 'Unexpected constructed condition')
        judgment = judgments[key]
        item = items[mapping[key]]
        s_id = key[:-1] + 'S'
        s_item = items[mapping[s_id]]
        require(row['item_id'] == mapping[key] and row['question'] == item['question']
                and row['raw_output'] == item['answer'] == predictions[key]['raw_output'],
                'Input/output join mismatch: ' + key)
        require(s_item['question'] == item['question'], 'S question differs')
        for mode, source_item in [('I', item), ('S', s_item)]:
            require(len(source_item['documents']) == 5, 'Wrong document count')
            for idx, doc in enumerate(source_item['documents'], 1):
                h = sha_bytes(doc.encode())
                label = f'{key}:{mode}:D{idx}'
                first = displayed.setdefault(h, label)
                inventory.append(dict(id=key, endpoint=mode, document_index=idx,
                                      sha256=h, first_display=first))
        require(judgment['primary_pattern'] in manual['primary_patterns'], 'Unknown pattern')
        require(judgment['boundary'] in {'none_identified', 'category_inference',
                'overview_scope', 'lexical_semantics', 'cause_vs_modifier', 'referent_ambiguity'},
                'Unknown interpretation boundary')
        ack = row['acknowledges_insufficiency']
        require(ack == old_ratings[row['item_id']]['acknowledges_insufficiency'],
                'Old acknowledgment changed')
        require((ack == 'yes') == (judgment['acknowledgment_alignment'] != 'none'),
                'Acknowledgment alignment mismatch')
        citations = []
        for mode, field, source_item in [('I', 'i_document_indices', item),
                                          ('S', 's_document_indices', s_item)]:
            indices = judgment[field]
            require(bool(indices) and len(set(indices)) == len(indices)
                    and all(type(i) is int and 1 <= i <= 5 for i in indices), 'Bad document indices')
            for idx in indices:
                text = source_item['documents'][idx - 1]
                citations.append(quote(text, text, idx, mode))
        absent = judgment['new_value']
        if judgment['primary_pattern'] == 'absent_answer_value':
            require(bool(absent) and absent.lower() in item['answer'].lower(), 'Missing answer value')
            require(all(absent.lower() not in d.lower() for d in item['documents']),
                    'Claimed absent value appears in I documents')
        else:
            require(absent is None, 'Absent-value claim outside its category')
        cases.append(dict(**judgment, item_id=row['item_id'], original_id=row['original_id'],
            partition=row['partition'], expression=row['expression'], question=item['question'],
            original_author_mode=row['exposed_author_input_mode'],
            original_has_substantive_answer=row['has_substantive_answer'],
            original_acknowledges_insufficiency=ack, original_rationale=row['rationale'],
            output=item['answer'], s_id=s_id, s_output=s_item['answer'],
            input_citations=citations, output_citation=quote(item['answer'], item['answer']),
            critical_output_citation=quote(item['answer'], judgment['critical_output_quote']),
            inference_provenance='unknown', original_judgments_overwritten=False))
    source_paths = [packet_path, mapping_path, predictions_path, BEHAVIOR + '-cells.csv',
        BEHAVIOR + '-ratings.json', MANUAL, RUN + '/approved_labels.json',
        'docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json',
        'scripts/semantic_transfer_insufficient_answer_audit.py']
    report = dict(status='posthoc_insufficient_answer_audit_complete', history_exposed=True,
        independent_gold=False, approved_for_training=False, formal_labels_added=0,
        original_judgments_overwritten=False, new_descriptive_case_codings=23,
        new_gpu_calls=0, new_answers=0, new_fits=0, remaining_original_design_fits=0,
        source_insufficient_rows=60, selected_outputs=len(cases),
        selected_bases=len({c['original_id'] for c in cases}),
        primary_pattern_counts=dict(Counter(c['primary_pattern'] for c in cases)),
        interpretation_boundary_counts=dict(Counter(c['boundary'] for c in cases)),
        acknowledgment_alignment_counts=dict(Counter(c['acknowledgment_alignment'] for c in cases)),
        attribution_counts=dict(Counter(c['attribution'] for c in cases)),
        input_citations=sum(len(c['input_citations']) for c in cases),
        output_citations=len(cases), critical_output_citations=len(cases),
        input_document_slots=len(inventory), unique_input_documents=len(displayed),
        preserved_original_paths=len(old_paths), preserved_fit_sealed_files=len(seal['files']),
        source_sha256={path: file_sha(path) for path in source_paths},
        interpretation='Selected outputs only; counts do not estimate all insufficient cases or population prevalence. Descriptive pattern is not causal provenance. New interpretation boundaries do not silently revise old input/behavior labels; none_identified is not independent semantic confirmation. S answers are retained even if they refused. No parametric-memory, external-world truth or probe-mechanism conclusions.',
        cases=cases)
    reading = dict(items=len(cases), slots=len(inventory), unique_documents=len(displayed),
        includes='All five documents at selected I and matched same-expression S endpoints',
        reading_declaration='Current history-exposed assistant read four displayed batches, with exact-text references for duplicates. Hashes bind texts, not semantic correctness or reader independence.',
        documents=inventory)
    return report, reading


def artifacts():
    report, reading = compute()
    cases = report['cases']
    columns = ['id', 'item_id', 'original_id', 'partition', 'expression', 'question',
        'required_fact', 'supplied_facts', 'unsupported_claim', 'primary_pattern', 'boundary',
        'assessment', 'original_acknowledges_insufficiency', 'acknowledgment_alignment',
        'attribution', 'new_value', 'inference_provenance', 'output', 's_id', 's_output']
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows({k: case[k] for k in columns} for case in cases)
    md = ['# 23条缺证作答逐条事实与依据表', '',
        '本表为有历史暴露的事后细分审计；23输出来自13底题，只按原作者refuse及原行为yes选取。三类编码描述文本现象，不认证内部机制。解释边界保留，不回写旧标签。S回答原样保留，不以其成功筛选对照。', '']
    for c in cases:
        md += [f"## {c['id']} / {c['item_id']}", '', f"问题：{c['question']}", '',
            f"需要的事实：{c['required_fact']}", '', f"I已提供：{c['supplied_facts']}", '',
            f"回答补出或挪用：{c['unsupported_claim']}", '',
            f"细分：{c['primary_pattern']}；解释边界：{c['boundary']}；不足表述对应：{c['acknowledgment_alignment']}；来源归因：unknown。", '',
            'I完整回答：', '', '> ' + c['output'], '',
            f"审计判断：{c['assessment']}", '', '可回放输入引用：', '']
        for citation in c['input_citations']:
            md += [f"- {citation['endpoint']} D{citation['document_index']}，字符[{citation['start']},{citation['end']})：{citation['quote']}"]
        md += ['', f"同题同表达S完整回答（仅描述）：{c['s_output']}", '']
    return {PREFIX + '.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        PREFIX + '-reading-inventory.json': json.dumps(reading, ensure_ascii=False, indent=2) + '\n',
        PREFIX + '-cases.csv': buf.getvalue(), PREFIX + '-cases.md': '\n'.join(md)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['analyze', 'verify'], required=True)
    args = parser.parse_args()
    outputs = artifacts()
    for path, content in outputs.items():
        data = content.encode()
        target = ROOT / path
        if args.stage == 'analyze':
            require(not target.exists() or target.read_bytes() == data, 'Refuse changed output: ' + path)
            target.write_bytes(data)
        else:
            require(target.read_bytes() == data, 'Replay mismatch: ' + path)
    report = json.loads(outputs[PREFIX + '.json'])
    print(json.dumps(dict(stage=args.stage, selected=report['selected_outputs'],
        bases=report['selected_bases'], patterns=report['primary_pattern_counts'],
        boundaries=report['interpretation_boundary_counts'],
        acknowledgments=report['acknowledgment_alignment_counts'],
        preserved_paths=report['preserved_original_paths'],
        fit_sealed_files=report['preserved_fit_sealed_files'], new_fits=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
