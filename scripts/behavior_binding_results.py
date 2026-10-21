"""Offline replay of sealed manual binding judgments; no generation, fitting or automatic scoring."""

import argparse
from collections import Counter
from datetime import datetime
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = 'runs/qwen2.5-3b-behavior-binding-v1'
PREFIX = 'docs/records/2026-10-21-behavior-binding-results'
FIELDS = ['has_substantive_target_answer', 'adopts_cell_distractor_value', 'supported_target_answer',
          'acknowledges_insufficiency', 'claimed_evidence_supports_target']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def check_files(files):
    for path, expected in files.items():
        require(digest(path) == expected, 'Preserved source changed: ' + path)


def check_quote(citation, text):
    require(type(citation['start']) is int and type(citation['end']) is int
        and 0 <= citation['start'] < citation['end'] <= len(text), 'Invalid quote offsets')
    require(text[citation['start']:citation['end']] == citation['quote']
        and hashlib.sha256(text.encode()).hexdigest() == citation['text_sha256'], 'Quote/text/hash mismatch')


def validate_ratings(packet, ratings):
    items = {r['item_id']: r for r in packet['items']}
    require(len(items) == len(packet['items']) == 48, 'Expected 48 anonymous inputs')
    rows = ratings['ratings']
    require(ratings['history_exposed'] is True and ratings['independent_gold'] is False
            and ratings['approved_for_training'] is False, 'Reviewer provenance changed')
    require(len(rows) == len({r['item_id'] for r in rows}) == 48
            and {r['item_id'] for r in rows} == set(items), 'Rating coverage/uniqueness mismatch')
    for row in rows:
        item = items[row['item_id']]
        require(row['status'] == 'reviewed' and bool(row['rationale']), 'Unreviewed judgment')
        require(all(row[f] in {'yes', 'no', 'unknown'} for f in FIELDS), 'Invalid behavior value')
        require(row['supported_target_answer'] != 'yes' or row['has_substantive_target_answer'] == 'yes',
                'Supported answer without target answer')
        require(row['adopts_cell_distractor_value'] != 'yes'
                or row['has_substantive_target_answer'] == 'yes', 'Adoption without target answer')
        require(bool(row['input_citations']) and bool(row['output_citations']), 'Missing judgment evidence')
        for citation in row['input_citations']:
            require(type(citation['document_index']) is int and 1 <= citation['document_index'] <= 5,
                    'Wrong evidence document index')
            check_quote(citation, item['documents'][citation['document_index'] - 1])
        for citation in row['output_citations']:
            check_quote(citation, item['answer'])
    return {r['item_id']: r for r in rows}


def rate(rows, field):
    counts = Counter(r[field] for r in rows)
    require(sum(counts.values()) > 0 and set(counts) <= {'yes', 'no', 'unknown'}, 'Invalid rate input')
    n, y, u = len(rows), counts['yes'], counts['unknown']
    return dict(eligible=n, yes=y, no=counts['no'], unknown=u,
                point=y/n if u == 0 else None, identification_lower=y/n, identification_upper=(y+u)/n)


def acknowledgment_then_answer(row):
    if row['has_substantive_target_answer'] == 'no' or row['acknowledges_insufficiency'] == 'no':
        return 'no'
    # A conjunction alone cannot establish output order. No source answer in this run needs this branch.
    return 'unknown'


def make_pairs(rows):
    require(len(rows) == len({r['id'] for r in rows}) == 48, 'Expected all48 unique cells')
    groups = {}
    for row in rows:
        group = groups.setdefault(row['original_id'], {})
        slot = row['condition'], row['variant']
        require(slot not in group, 'Duplicate condition/variant')
        group[slot] = row
    require(len(groups) == 12, 'Expected12 base scenarios')
    pairs = []
    for base, group in sorted(groups.items()):
        require(set(group) == {(s, v) for s in ['S', 'I'] for v in ['v1', 'v2']}, 'Incomplete four-cell base')
        require(len({r['question'] for r in group.values()}) == 1
                and len({r['target_entity'] for r in group.values()}) == 1, 'Mixed base/question')
        pair = dict(original_id=base, question=group['S', 'v1']['question'])
        for (condition, variant), row in group.items():
            tag = condition + '_' + variant
            pair[tag + '_id'] = row['id']
            pair[tag + '_item_id'] = row['item_id']
            pair[tag + '_output'] = row['raw_output']
            for field in FIELDS:
                pair[tag + '_' + field] = row[field]
        def both(a, b):
            return 'no' if 'no' in [a, b] else 'unknown' if 'unknown' in [a, b] else 'yes'
        pair['I_both_follow_cell_distractor'] = both(group['I', 'v1']['adopts_cell_distractor_value'],
                                                     group['I', 'v2']['adopts_cell_distractor_value'])
        pair['S_both_supported'] = both(group['S', 'v1']['supported_target_answer'],
                                        group['S', 'v2']['supported_target_answer'])
        pair['I_neither_target_answer'] = both(
            {'yes':'no', 'no':'yes', 'unknown':'unknown'}[group['I', 'v1']['has_substantive_target_answer']],
            {'yes':'no', 'no':'yes', 'unknown':'unknown'}[group['I', 'v2']['has_substantive_target_answer']])
        pairs.append(pair)
    return pairs


def compute():
    seal = read(PREFIX + '-seal.json')
    require(seal['independent_gold'] is False, 'Seal cannot confer semantic independence')
    check_files(seal['files'])
    check_files(read('docs/records/2026-10-21-behavior-binding-preparation-preserved.json'))
    prepared = read('docs/records/2026-10-21-behavior-binding-preparation.json')
    check_files(prepared['prepared_artifact_sha256'])
    source_files = read(PREFIX + '-source-run-hashes.json')
    check_files(source_files)
    actual = {str(p.relative_to(ROOT)) for p in (ROOT / RUN).rglob('*') if p.is_file() and p.name != '.run.lock'}
    require(actual == set(source_files), 'Original run file set changed')
    packet = read(RUN + '/behavior_review/packet.json')
    ratings = read(PREFIX + '-ratings.json')
    require(digest(RUN + '/behavior_review/packet.json') == seal['packet_sha256'] == ratings['packet_sha256']
            and digest('prompts/behavior_binding_scoring_v1.json') == seal['rubric_sha256'] == ratings['rubric_sha256'],
            'Wrong packet/rubric binding')
    judgments = validate_ratings(packet, ratings)
    manual = read(PREFIX + '-manual.json')
    require(manual['field_order'] == FIELDS, 'Handwritten field order changed')
    for entry in manual['ratings']:
        require(all(judgments[entry['item_id']][f] == {'Y':'yes','N':'no','U':'unknown'}[code]
            for f, code in zip(FIELDS, entry['codes'])) and len(entry['codes']) == 5, 'Handwritten judgment mismatch')
    # Coordinator mapping is joined only after verifying the pre-join judgment seal.
    mapping = read(RUN + '/coordinator/behavior_mapping.json')
    materials = read(RUN + '/materials/inputs.json')
    predictions = read(RUN + '/predictions.json')['records']
    items = {r['item_id']:r for r in packet['items']}
    pred = {r['id']:r for r in predictions}
    require(len(mapping) == len(materials) == len(pred) == 48
            and set(mapping.values()) == set(judgments), 'Coordinator join size mismatch')
    rows = []
    for material in materials:
        key = material['id']
        item = items[mapping[key]]
        prediction = pred[key]
        judgment = judgments[mapping[key]]
        require(material['question'] == item['question'] and material['docs'] == item['documents']
                and prediction['raw_output'] == item['answer'], 'Input/output join mismatch')
        require(all(material[k] == prediction[k] for k in ['original_id', 'condition', 'variant']), 'Cell provenance mismatch')
        rows.append(dict(**{k: material[k] for k in ['id', 'original_id', 'condition', 'variant', 'question',
            'target_entity', 'distractor_entity', 'target_value', 'distractor_value', 'target_slot', 'distractor_slot']},
            item_id=judgment['item_id'], raw_output=item['answer'], **{f: judgment[f] for f in FIELDS},
            rationale=judgment['rationale'], input_tokens=prediction['input_tokens'],
            generated_tokens=prediction['generated_tokens'],
            acknowledgment_then_answer=acknowledgment_then_answer(judgment)))
    pairs = make_pairs(rows)
    def summarize(group):
        return dict(cells=len(group), bases=len({r['original_id'] for r in group}),
                    fields={f:rate(group, f) for f in FIELDS},
                    acknowledgment_then_answer=rate(group, 'acknowledgment_then_answer'))
    summary = dict(status='history_exposed_binding_behavior_review_complete', independent_gold=False,
        history_exposed=True, formal_labels_added=0, new_gpu_calls=0, new_answers=0, new_probe_fits=0,
        actual_collected_answers=48, source_run_preserved_files=len(source_files),
        prior_preserved_paths=prepared['preserved_paths'], original_fit_budget_remaining=0,
        reviewed_rows=48, rated_fields=240, determinate_fields=sum(r[f]!='unknown' for r in rows for f in FIELDS),
        unknown_fields=sum(r[f]=='unknown' for r in rows for f in FIELDS),
        input_citations=sum(len(r['input_citations']) for r in judgments.values()),
        output_citations=sum(len(r['output_citations']) for r in judgments.values()),
        all=summarize(rows), by_condition={s:summarize([r for r in rows if r['condition']==s]) for s in ['S','I']},
        by_condition_variant={s+'_'+v:summarize([r for r in rows if r['condition']==s and r['variant']==v])
                              for s in ['S','I'] for v in ['v1','v2']},
        paired_bases={f:rate(pairs,f) for f in ['I_both_follow_cell_distractor','S_both_supported','I_neither_target_answer']},
        source_collection=read(RUN + '/reports/collection.json'),
        timing=dict(generation_seconds=sum(r['elapsed_seconds'] for r in predictions),
            first_completion=predictions[0]['completed_at'],last_completion=predictions[-1]['completed_at'],
            first_inference_to_last_save_seconds=(datetime.fromisoformat(predictions[-1]['completed_at'])-
                datetime.fromisoformat(predictions[0]['completed_at'])).total_seconds()+predictions[0]['elapsed_seconds']),
        sampling_intervals_computed=False,
        interpretation='12 fictional identifier/position scenarios in one English sentence family. Zero observed errors is not a population-zero guarantee; variants are clustered by scenario. No bootstrap confidence claim, independent semantic gold, natural-document generalization, parameter-memory or hidden-state mechanism inference. Generic According to records is not a specific evidence citation; its field remains unknown, not failure.',
        implementation_sha256=digest('scripts/behavior_binding_results.py'),
        tests_sha256=digest('tests/test_behavior_binding_results.py'),
        judgment_seal_sha256=digest(PREFIX + '-seal.json'))
    return summary, rows, pairs


def csv_text(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['analyze', 'verify'], required=True)
    args = parser.parse_args()
    report, rows, pairs = compute()
    outputs = {PREFIX+'.json':json.dumps(report,ensure_ascii=False,indent=2)+'\n',
               PREFIX+'-cells.csv':csv_text(rows), PREFIX+'-pairs.csv':csv_text(pairs)}
    for path, content in outputs.items():
        target = ROOT / path
        data = content.encode()
        if target.exists():
            require(target.read_bytes()==data, 'Frozen analysis changed: '+path)
        else:
            require(args.stage=='analyze', 'Missing analysis artifact: '+path)
            target.write_bytes(data)
    print(json.dumps(dict(stage=args.stage,reviewed_rows=48,
        I_distractor_adoption=report['by_condition']['I']['fields']['adopts_cell_distractor_value'],
        S_supported=report['by_condition']['S']['fields']['supported_target_answer'],
        unknown_fields=report['unknown_fields'],new_fits=0),ensure_ascii=False))


if __name__ == '__main__':
    main()
