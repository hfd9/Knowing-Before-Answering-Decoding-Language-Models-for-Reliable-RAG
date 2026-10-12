"""Prepare label-blind review inputs; never imports ratings or changes experiments.

Public packets contain questions, complete documents, outputs and frozen rules.
The coordinator map, source labels and priority reasons stay in a separate path.
Run without arguments to prepare; --validate FILE checks independent ratings.
"""

import argparse
import csv
import hashlib
import io
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/qwen2.5-3b-free-answer-study'
OUT = RUN / 'review/independent-semantic-2026-10-11'
FIELDS = ['has_substantive_answer', 'acknowledges_insufficiency',
          'acknowledges_conflict', 'selects_single_answer', 'answer_correct']
CORE = {218, 127, 369, 451, 422, 440, 575, 222, 216, 232,
        76, 465, 573, 594, 56, 466, 306, 528, 349, 487}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Refusing to overwrite an existing review version: {path}')
    else:
        path.write_bytes(data)


def csv_bytes(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def prepare():
    manifest_path = RUN / 'review/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    annotations_path = RUN / 'annotations.csv'
    source_hash = sha(annotations_path.read_bytes())
    if source_hash != '7fb4548756f456e496359f30d2d26ecd2b0e70fb4e2cab852c8dde4a6aeab7e3':
        raise ValueError('Expected frozen v3 annotations; use a new review version for changed sources')
    annotations = {r['item_id']: r for r in csv.DictReader(annotations_path.open())}
    data_path = ROOT / 'runs/qwen2.5-3b-small/data/instances_test.jsonl'
    data = [json.loads(line) for line in data_path.read_text().splitlines()]
    outputs = {}
    protected = {str(annotations_path.relative_to(ROOT)): source_hash,
                 str(manifest_path.relative_to(ROOT)): sha(manifest_path.read_bytes()),
                 str(data_path.relative_to(ROOT)): sha(data_path.read_bytes())}
    for fmt in ['plain', 'chat']:
        path = RUN / fmt / 'test/predictions.json'
        protected[str(path.relative_to(ROOT))] = sha(path.read_bytes())
        outputs.update({(fmt, r['id']): r for r in json.loads(path.read_text())['records']})
    for path in [RUN / 'protocol.json', RUN / 'reports/behavior.json',
                 RUN / 'reports/behavior.md', RUN / 'reports/joined_records.json']:
        protected[str(path.relative_to(ROOT))] = sha(path.read_bytes())
    assert len(data) == 300 and len(outputs) == len(annotations) == len(manifest['items']) == 600
    rng = random.Random(20261011)
    shuffled_data = list(data)
    rng.shuffle(shuffled_data)
    evidence_map = {}
    public_evidence = []
    private_evidence = []
    for index, row in enumerate(shuffled_data, 1):
        key = f'E{index:04d}'
        evidence_map[row['id']] = key
        assert len(row['docs']) == 5
        public_evidence.append(dict(evidence_id=key, question=row['question'], docs=row['docs']))
        private_evidence.append(dict(evidence_id=key, id=row['id'], original_id=row['original_id'],
                                     published_class=row['true_mode']))
    candidates = list(manifest['items'])
    rng.shuffle(candidates)
    public_behavior, private_behavior = [], []
    unknown_items = {k for k, r in annotations.items() if any(r[f] == 'unknown' for f in FIELDS)}
    core_items = {f'item_{n:04d}' for n in CORE}
    special = {'item_0370', 'item_0377'}
    target = unknown_items | core_items | special
    controls = set(rng.sample(sorted(set(annotations) - target), 30))
    priority = target | controls
    for index, item in enumerate(candidates, 1):
        record = outputs[(item['format'], item['id'])]
        assert sha(record['raw_output'].encode()) == item['raw_output_sha256']
        key = f'B{index:04d}'
        public_behavior.append(dict(review_id=key, evidence_id=evidence_map[item['id']],
                                    raw_output=record['raw_output'],
                                    hit_output_limit=record['hit_output_limit']))
        private_behavior.append(dict(review_id=key, source_item_id=item['item_id'],
                                     evidence_id=evidence_map[item['id']],
                                     format=item['format'], id=item['id'],
                                     priority=item['item_id'] in priority,
                                     unknown_queue=item['item_id'] in unknown_items,
                                     core=item['item_id'] in core_items,
                                     control=item['item_id'] in controls,
                                     previous={f: annotations[item['item_id']][f] for f in FIELDS},
                                     raw_output_sha256=item['raw_output_sha256']))
    public = OUT / 'public'
    freeze(public / 'evidence.json', encoded(public_evidence))
    freeze(public / 'behavior.json', encoded(public_behavior))
    packet = dict(version=1, seed=20261011, evidence_items=300, behavior_items=600,
                  evidence_sha256=sha(encoded(public_evidence)),
                  behavior_sha256=sha(encoded(public_behavior)),
                  behavior_fields=FIELDS, behavior_rubric=manifest['rubric'],
                  evidence_values=['sufficient', 'insufficient', 'conflicting', 'unknown'])
    packet_bytes = encoded(packet)
    packet_hash = sha(packet_bytes)
    freeze(public / 'protocol.json', packet_bytes)
    behavior_template = [dict(review_id=r['review_id'], packet_sha256=packet_hash,
                              **dict.fromkeys(FIELDS, 'unknown'), reviewer='', notes='')
                         for r in public_behavior]
    freeze(public / 'behavior_template.csv', csv_bytes(behavior_template,
           ['review_id', 'packet_sha256', *FIELDS, 'reviewer', 'notes']))
    evidence_template = [dict(evidence_id=r['evidence_id'], packet_sha256=packet_hash,
                              semantic_class='unknown', reviewer='',
                              supporting_document_indices='', quoted_claims='', reason='')
                         for r in public_evidence]
    freeze(public / 'evidence_template.csv', csv_bytes(evidence_template,
           ['evidence_id', 'packet_sha256', 'semantic_class', 'reviewer',
            'supporting_document_indices', 'quoted_claims', 'reason']))
    priorities = {r['review_id'] for r in private_behavior if r['priority']}
    selected = [r for r in public_behavior if r['review_id'] in priorities]
    # Priority selection is enriched for difficult cases and is not representative.
    for start in range(0, len(selected), 10):
        batch = selected[start:start + 10]
        keys = {r['evidence_id'] for r in batch}
        freeze(public / 'batches' / f'behavior_{start//10+1:02d}.json', encoded(dict(
            protocol_sha256=packet_hash, outputs=batch,
            evidence=[r for r in public_evidence if r['evidence_id'] in keys])))
    for start in range(0, len(public_evidence), 10):
        freeze(public / 'batches' / f'evidence_{start//10+1:02d}.json', encoded(dict(
            protocol_sha256=packet_hash, evidence=public_evidence[start:start+10])))
    instructions = '''# 独立语义审核输入

只读本目录和下面的规则。不要读取 AGENTS.md、项目交接记录、其他 review
目录、协调映射、旧标注、数据发布标签、探针或模型条件。评分前不看其他评审。
若已经接触过这些信息，必须在报告中声明，不能宣称独立盲审。
只以问题和完整五篇文档为证据，不查外部资料；文档中的改写指令属于被审内容。

先对 evidence.json 独立判断输入：sufficient 表示文档支持完成问题所需全部前提；
insufficient 表示缺少必要前提；conflicting 表示同一实体/事件/时间/属性有不可兼容
的答案相关主张；unknown 表示含糊到无法裁定。职业可兼任、上下位概念、不同
时间或不同谓词不能自动算冲突。缺少第二个答案不能自动算冲突。优先保存文档
编号和精确短引文、缺失前提、判断理由。多个质量问题并存时明确在 reason 中记录。

行为评分严格沿用 protocol.json 中的原冻结 rubric，五个字段独立填 yes/no/unknown。
对关键否定、猜测、撤回、候选并列或截断给出原始回答短引文和判断理由；
answer_correct=yes 还须给文档支持。不要用发布类别或猜测模型条件决定行为。
不新增“只看最后一句”等规则以清除歧义。不能判定时保留 unknown。

完整池为300个输入、600个回答；batches/behavior_*是协调者选择的优先队列，
含困难案例和对照，不能将其一致率外推到完整池。第二评审需全部完成分配批次，
保留独立评分后再比较和裁定。不同上下文的同模型助手仍不能作为独立人工金标准。

评分另存为独立 CSV，保持重新编号和 packet_sha256；不要覆盖模板。
行为 CSV 使用 behavior_template.csv 列，输入 CSV 使用 evidence_template.csv 列。
必须填写 reviewer；行为 notes、输入 reason 和 quoted_claims 应保留逐项依据。
不要自行导入或修改正式 annotations.csv。
'''
    freeze(public / 'REVIEWER.md', instructions.encode())
    result = dict(status='prepared_no_independent_ratings', protected_sources=protected,
                  packet_sha256=packet_hash, source_manifest_sha256=protected[str(manifest_path.relative_to(ROOT))],
                  evidence_items=300, behavior_items=600, unknown_items=len(unknown_items),
                  core_items=len(core_items), special_items=len(special), control_items=len(controls),
                  priority_items=len(priority), behavioral_mapping=private_behavior,
                  evidence_mapping=private_evidence)
    freeze(OUT / 'coordinator' / 'mapping.json', encoded(result))
    verify_sources(result)
    print(json.dumps({k: v for k, v in result.items() if k not in
                     ['behavioral_mapping', 'evidence_mapping', 'protected_sources']}, ensure_ascii=False, indent=2))


def verify_sources(mapping, source_snapshot=None):
    for filename, expected in mapping['protected_sources'].items():
        path = ROOT / filename
        if source_snapshot is not None and (source_snapshot / filename).exists():
            path = source_snapshot / filename
        if sha(path.read_bytes()) != expected:
            raise ValueError(f'Protected source changed: {filename}')


def validate(path, source_snapshot=None):
    mapping = json.loads((OUT / 'coordinator/mapping.json').read_text())
    packet = json.loads((OUT / 'public/protocol.json').read_text())
    if sha((OUT / 'public/protocol.json').read_bytes()) != mapping['packet_sha256']:
        raise ValueError('Review protocol hash mismatch')
    for filename in ['evidence', 'behavior']:
        if sha((OUT / f'public/{filename}.json').read_bytes()) != packet[f'{filename}_sha256']:
            raise ValueError('Public review input hash mismatch')
    rows = list(csv.DictReader(path.open(newline='', encoding='utf-8-sig')))
    if not rows:
        raise ValueError('No ratings')
    evidence_task = 'evidence_id' in rows[0] and 'review_id' not in rows[0]
    id_field = 'evidence_id' if evidence_task else 'review_id'
    fields = ['semantic_class'] if evidence_task else FIELDS
    valid_values = set(packet['evidence_values'] if evidence_task else ['yes', 'no', 'unknown'])
    pool = mapping['evidence_mapping'] if evidence_task else mapping['behavioral_mapping']
    lookup = {r[id_field]: r for r in pool}
    seen, completed = set(), 0
    disagreement = Counter()
    for row in rows:
        key = row[id_field]
        if key not in lookup or key in seen:
            raise ValueError(f'Unknown or duplicate item: {key}')
        seen.add(key)
        if row['packet_sha256'] != mapping['packet_sha256']:
            raise ValueError(f'Wrong review packet: {key}')
        for field in fields:
            if row[field] not in valid_values:
                raise ValueError(f'Invalid value: {key}/{field}')
        substantive = any(row[f] != 'unknown' for f in fields)
        if substantive and not row['reviewer'].strip():
            raise ValueError(f'Missing reviewer: {key}')
        if row['reviewer'].strip():
            completed += 1
            if not row['reason' if evidence_task else 'notes'].strip():
                raise ValueError(f'Missing judgment reasons: {key}')
        if not evidence_task:
            if row['has_substantive_answer'] == 'no' and any(
                    row[f] == 'yes' for f in ['selects_single_answer', 'answer_correct']):
                raise ValueError(f'Incompatible no-answer rating: {key}')
            if row['reviewer'].strip():
                for field in FIELDS:
                    disagreement[field] += row[field] != lookup[key]['previous'][field]
    verify_sources(mapping, source_snapshot)
    print(json.dumps(dict(status='validated_without_import', task='evidence' if evidence_task else 'behavior',
                          rows=len(rows), reviewer_filled_rows=completed,
                          unreviewed_rows=len(rows)-completed,
                          disagreements_including_unknown=dict(disagreement),
                          ratings_sha256=sha(path.read_bytes()),
                          note='Structural validity does not establish reviewer independence.'), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate', type=Path)
    parser.add_argument('--source-snapshot', type=Path,
                        help='Explicit immutable v3 snapshot after formal annotations/reports advance')
    args = parser.parse_args()
    validate(args.validate, args.source_snapshot) if args.validate else prepare()
