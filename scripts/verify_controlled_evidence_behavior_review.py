"""Read-only provenance and independent counts for the explicit 40-item behavior review."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/qwen2.5-3b-controlled-evidence-pilot-v1'
PREFIX = ROOT / 'docs/records/2026-10-20-controlled-evidence-pilot-behavior'
FIELDS = ['has_substantive_answer', 'acknowledges_insufficiency',
          'acknowledges_conflict', 'selects_single_answer', 'answer_correct']


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(records, field):
    n = len(records)
    yes = sum(r['behavior'][field] == 'yes' for r in records)
    no = sum(r['behavior'][field] == 'no' for r in records)
    unknown = n - yes - no
    return dict(denominator=n, known_positive=yes, known_negative=no, unknown=unknown,
                rate=yes / n if n and not unknown else None,
                lower_bound=yes / n if n else None,
                upper_bound=(yes + unknown) / n if n else None)


def inspect():
    folder = BASE / 'review/assistant-behavior-2026-10-20-v1'
    ratings = read(folder / 'ratings.json')
    seal = read(folder / 'seal.json')
    require(not ratings['independent_gold'] and not seal['independent_gold'], 'Exposure disclosure lost')
    for filename in ['ratings.json', 'annotations.csv']:
        require((folder / filename).read_bytes() ==
                Path(str(PREFIX) + '-ratings.' + filename.split('.')[-1]).read_bytes(),
                'Durable review copy differs')
    require(digest(folder / 'ratings.json') == seal['ratings_sha256'], 'Ratings seal differs')
    require(digest(folder / 'annotations.csv') == seal['annotations_sha256'], 'CSV seal differs')
    for name, expected in ratings['source_sha256'].items():
        path = BASE / name
        if name.startswith('reports/'):
            path = BASE / 'reports/history' / ratings['source_sha256']['reports/pilot.json'] / Path(name).name
        require(digest(path) == expected, f'Original source/history differs: {name}')
    protocol = read(BASE / 'protocol.json')
    for name, expected in {**protocol['implementation_sha256'], **protocol['probe_source_sha256']}.items():
        require(digest(ROOT / name) == expected, f'Frozen dependency differs: {name}')
    inputs = {r['id']: r for r in read(BASE / 'materials/inputs.json')}
    require(len(inputs) == 40 and sum(len(r['docs']) for r in inputs.values()) == 200 and
            len({text for r in inputs.values() for text in r['docs']}) == 89,
            'Source document coverage differs')
    outputs = {r['id']: r for r in read(BASE / 'free_answer/predictions.json')['records']}
    labels = {r['id']: r for r in read(BASE / 'classification/predictions.json')['records']}
    manifest = {r['item_id']: r for r in read(BASE / 'review/manifest.json')['items']}
    with (folder / 'annotations.csv').open(newline='', encoding='utf-8') as f:
        csv_rows = list(csv.DictReader(f))
    require(len(csv_rows) == len(manifest) == len(ratings['ratings']) == 40, 'Expected 40 rows')
    by_ticket = {r['item_id']: r for r in csv_rows}
    require(len(by_ticket) == 40, 'Duplicate CSV ticket')
    records, citation_count = [], 0
    for item in ratings['ratings']:
        ticket, key = item['item_id'], item['id']
        require(manifest[ticket]['id'] == key, 'Anonymous mapping differs')
        original, output, line = inputs[key], outputs[key], by_ticket[ticket]
        require(line['review_manifest_sha256'] == digest(BASE / 'review/manifest.json'), 'Wrong batch')
        require(line['reviewer'] == ratings['reviewer'] and line['notes'] == item['rationale'], 'Reviewer/rationale differs')
        require(item['read_doc_slots'] == [1, 2, 3, 4, 5], 'Incomplete document coverage')
        require(item['question_sha256'] == hashlib.sha256(original['question'].encode()).hexdigest(), 'Question differs')
        require(item['raw_output_sha256'] == manifest[ticket]['raw_output_sha256'] ==
                hashlib.sha256(output['raw_output'].encode()).hexdigest(), 'Output differs')
        for field in FIELDS:
            require(item['behavior'][field] in ['yes', 'no', 'unknown'] and
                    line[field] == item['behavior'][field], 'Rating/CSV differs')
        require(item['behavior']['has_substantive_answer'] != 'no' or
                all(item['behavior'][f] != 'yes' for f in ['selects_single_answer', 'answer_correct']),
                'Incompatible no-answer rating')
        for quote in item['citations']:
            text = original['docs'][quote['doc_slot'] - 1]
            require(text[quote['start']:quote['end']] == quote['quote'] and
                    hashlib.sha256(text.encode()).hexdigest() == quote['document_sha256'], 'Input citation differs')
            citation_count += 1
        quote = item['output_citation']
        require(output['raw_output'][quote['start']:quote['end']] == quote['quote'], 'Output citation differs')
        records.append(dict(item, condition=original['condition'], original_id=original['original_id'],
                            probe=output['probe_pred'], classification=labels[key]['pred_mode']))
    require(len({r['id'] for r in records}) == 40 and citation_count == 80, 'Coverage/citation count differs')
    report = read(BASE / 'reports/pilot.json')
    require(report['annotation_sha256'] == seal['annotations_sha256'] and
            Path(report['annotation_file']) == folder / 'annotations.csv', 'Report consumed a different review')
    require(digest(BASE / 'review/annotation_snapshots' / (seal['annotations_sha256'] + '.csv')) ==
            seal['annotations_sha256'], 'Consumed snapshot differs')
    groups = {c: [r for r in records if r['condition'] == c] for c in 'SICD'}
    require(all(len(g) == 10 for g in groups.values()), 'Expected 10 per condition')
    rows = groups['I']
    predicates = {
        'all_refuse_substantive_answer_rate': (rows, 'has_substantive_answer'),
        'refuse_probe_refuse_then_answer_rate': ([r for r in rows if r['probe'] == 'refuse'], 'has_substantive_answer'),
        'refuse_probe_other_then_answer_rate': ([r for r in rows if r['probe'] != 'refuse'], 'has_substantive_answer'),
        'all_conflict_select_single_answer_rate': (groups['C'], 'selects_single_answer'),
        'conflict_probe_conflict_then_select_rate': ([r for r in groups['C'] if r['probe'] == 'conflict'], 'selects_single_answer'),
        'all_conflict_acknowledgement_rate': (groups['C'], 'acknowledges_conflict'),
        'all_answer_substantive_answer_rate': (groups['S'], 'has_substantive_answer'),
    }
    independent = {}
    for key, (selected, field) in predicates.items():
        value = bounds(selected, field)
        require(all(report['main']['behavior']['rates'][key][k] == v for k, v in value.items()), f'Rate differs: {key}')
        independent[key] = value
    for key, predicate in {
        'all_answer_grounded_correct_rate': lambda r: r['behavior']['has_substantive_answer'] == 'yes' and r['behavior']['answer_correct'] == 'yes',
        'all_answer_no_substantive_answer_rate': lambda r: r['behavior']['has_substantive_answer'] == 'no',
        'all_answer_explicit_insufficiency_refusal_rate': lambda r: r['behavior']['has_substantive_answer'] == 'no' and r['behavior']['acknowledges_insufficiency'] == 'yes',
    }.items():
        count = sum(predicate(r) for r in groups['S'])
        saved = report['main']['behavior']['rates'][key]
        require(saved['known_positive'] == count and saved['denominator'] == 10 and saved['rate'] == count / 10, key)
    selected_answer = sum(r['probe'] == 'refuse' and r['behavior']['has_substantive_answer'] == 'yes' for r in groups['I'])
    share = report['main']['behavior']['rates']['refuse_recognized_then_answer_share_of_all_refuse']
    require(share['known_positive'] == selected_answer and share['denominator'] == 10 and share['rate'] == selected_answer / 10, 'Refuse share differs')
    quartets = []
    for oid in sorted({r['original_id'] for r in records}, key=lambda x: int(x.split('_')[-1])):
        g = {r['condition']: r for r in records if r['original_id'] == oid}
        quartets.append(dict(original_id=oid, conditions={c: {k: g[c][k] for k in ['id', 'item_id', 'probe', 'classification', 'behavior']} for c in 'SICD'}))
    for field in FIELDS:
        known = [q for q in quartets if all(q['conditions'][c]['behavior'][field] != 'unknown' for c in ['S', 'D'])]
        equal = sum(q['conditions']['S']['behavior'][field] == q['conditions']['D']['behavior'][field] for q in known)
        saved = report['control']['behavior_invariance'][field]
        require(saved['known_equal'] == equal and saved['unknown_pairs'] == 10 - len(known) and saved['denominator'] == 10, 'D invariance differs')
    unknown = [{'item_id': r['item_id'], 'id': r['id'], 'field': f} for r in records for f in FIELDS if r['behavior'][f] == 'unknown']
    require(len(unknown) == 2 and report['unknown_behavior_rows'] == len({r['id'] for r in unknown}) == 2, 'Unknown count differs')
    table_columns = ['id', 'item_id', 'original_id', 'condition', 'probe', 'classification', *FIELDS, 'rationale']
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=table_columns, lineterminator='\n')
    writer.writeheader()
    for r in sorted(records, key=lambda x: x['id']):
        writer.writerow({**{k: r[k] for k in table_columns if k not in FIELDS}, **r['behavior']})
    summary = dict(status='explicit_review_and_independent_counts_verified_with_2_unknown_fields',
                   rows=40, known_fields=198, unknown_fields=unknown, input_citations=80, output_citations=40,
                   source_documents_read=89, source_slots_read=200, independent_gold=False,
                   reviewer=ratings['reviewer'], annotation_sha256=seal['annotations_sha256'],
                   ratings_sha256=seal['ratings_sha256'], report_sha256=digest(BASE / 'reports/pilot.json'),
                   old_unscored_report_sha256=ratings['source_sha256']['reports/pilot.json'],
                   behavior_counts_by_condition={c: {f: bounds(g, f) for f in FIELDS} for c, g in groups.items()},
                   independent_main_rates=independent,
                   conflict_acknowledged_and_selected=[r['id'] for r in groups['C'] if r['behavior']['acknowledges_conflict'] == r['behavior']['selects_single_answer'] == 'yes'],
                   sufficient_probe_conflict_but_grounded=[r['id'] for r in groups['S'] if r['probe'] == 'conflict' and r['behavior']['answer_correct'] == 'yes'],
                   quartets=quartets, limitation='Same exposed assistant/material author; descriptive development findings, no independent gold, generalization or causal mechanism claim.')
    return summary, text.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write_new_summary', action='store_true', help='Create new durable summary/CSV once; never overwrite')
    args = parser.parse_args()
    summary, table = inspect()
    targets = {Path(str(PREFIX) + '-summary.json'): json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
               Path(str(PREFIX) + '-comparison.csv'): table}
    for path, content in targets.items():
        if args.write_new_summary:
            with path.open('x', encoding='utf-8', newline='') as f:
                f.write(content)
        else:
            require(path.read_bytes() == content.encode('utf-8'), f'Durable summary differs: {path}')
    print(json.dumps({k: summary[k] for k in ['status', 'rows', 'known_fields', 'unknown_fields', 'input_citations',
                                             'output_citations', 'conflict_acknowledged_and_selected',
                                             'sufficient_probe_conflict_but_grounded']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
