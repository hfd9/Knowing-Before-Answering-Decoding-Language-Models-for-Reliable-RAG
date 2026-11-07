"""Check a review batch's structure, exact citations, and visible input presentation.

Reads only the supplied anonymous packet, reviewer response and visible CLI events.
It does not inspect conditions or score semantic correctness/independence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def verify(packet_path, response_path, events_path, start, end):
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    require(set(packet) == {'items'} and len(packet['items']) == 48, 'invalid anonymous packet')
    items = {x['item_id']: x for x in packet['items']}
    expected = [f'P{i:03d}' for i in range(start, end + 1)]
    require(len(items) == 48 and all(x in items for x in expected), 'packet ID inventory differs')
    response = json.loads(response_path.read_text())
    require(set(response) == {'reviewer_id', 'batch', 'input_packet_sha256', 'items',
                              'exposure_statement', 'reading_statement', 'limitations'},
            'unexpected review response keys')
    require(response['reviewer_id'] == 'SCOPECLI20261107R01', 'unexpected reviewer')
    require(response['batch'] == f'P{start:03d}-P{end:03d}', 'unexpected batch')
    require(response['input_packet_sha256'] == hashlib.sha256(raw).hexdigest(), 'packet fingerprint differs')
    require(all(isinstance(response[k], str) and response[k].strip()
                for k in ('exposure_statement', 'reading_statement', 'limitations')), 'missing provenance narrative')
    reviewed = response['items']
    require(isinstance(reviewed, list) and len(reviewed) == len(expected)
            and {x.get('item_id') for x in reviewed} == set(expected), 'missing or duplicated item')
    item_keys = {'item_id', 'target_entity', 'target_field', 'target_record_state', 'target_records',
                 'conflicts', 'target_support_interpretation', 'missing_or_uncertain',
                 'reasoning', 'evidence_citations'}
    quote_count = 0

    def citation(cite, source, with_value):
        nonlocal quote_count
        expected_keys = {'document_index', 'quote', 'value'} if with_value else {'document_index', 'quote'}
        require(isinstance(cite, dict) and set(cite) == expected_keys, 'bad citation fields')
        index, quote = cite['document_index'], cite['quote']
        require(type(index) is int and 1 <= index <= 5 and isinstance(quote, str) and quote.strip(),
                'bad citation location')
        require(quote in source['documents'][index - 1], 'quote not present in specified document')
        if with_value:
            require(isinstance(cite['value'], str) and cite['value'] and cite['value'] in quote,
                    'record value absent from quote')
        quote_count += 1

    for row in reviewed:
        require(set(row) == item_keys, 'unexpected reviewed item fields')
        source = items[row['item_id']]
        require(len(source['documents']) == 5, 'wrong source slot count')
        require(isinstance(row['target_entity'], str) and row['target_entity'] in source['question'],
                'target entity absent from question')
        require(isinstance(row['target_field'], str) and row['target_field'] in source['question'],
                'target field absent from question')
        require(row['target_record_state'] in ('no_target_record', 'target_record_supported',
                                               'conflicting_target_records', 'unknown'), 'invalid state')
        for key in ('target_support_interpretation', 'missing_or_uncertain', 'reasoning'):
            require(isinstance(row[key], str) and row[key].strip(), 'empty interpretation')
        require(isinstance(row['target_records'], list), 'target records must be a list')
        require(isinstance(row['conflicts'], list), 'conflicts must be a list')
        require(isinstance(row['evidence_citations'], list) and row['evidence_citations'], 'missing citations')
        for record in row['target_records']:
            citation(record, source, True)
        for conflict in row['conflicts']:
            require(isinstance(conflict, dict) and set(conflict) == {'entity', 'field', 'records', 'reason'},
                    'invalid conflict structure')
            require(all(isinstance(conflict[k], str) and conflict[k].strip()
                        for k in ('entity', 'field', 'reason')), 'empty conflict details')
            require(isinstance(conflict['records'], list) and len(conflict['records']) >= 2,
                    'conflict requires two records')
            for record in conflict['records']:
                citation(record, source, True)
        for cite in row['evidence_citations']:
            citation(cite, source, False)

    presented = {}
    with events_path.open() as stream:
        for line in stream:
            event = json.loads(line)
            event_item = event.get('item', {})
            if event.get('type') != 'item.completed' or event_item.get('type') != 'command_execution':
                continue
            for output_line in event_item.get('aggregated_output', '').splitlines():
                try:
                    value = json.loads(output_line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict) and value.get('item_id') in expected:
                    require(value == items[value['item_id']], 'displayed input differs from source')
                    presented[value['item_id']] = True
    require(set(presented) == set(expected), 'full input presentation not observed for every item')
    return {'status': 'structure_citations_visible_text_verified_not_semantics_or_independence',
            'batch': response['batch'], 'reviewed_items': len(reviewed), 'exact_quote_occurrences': quote_count,
            'visible_complete_items': len(presented), 'declared_states': dict(Counter(x['target_record_state'] for x in reviewed)),
            'packet_sha256': hashlib.sha256(raw).hexdigest(),
            'response_sha256': hashlib.sha256(response_path.read_bytes()).hexdigest(),
            'events_sha256': hashlib.sha256(events_path.read_bytes()).hexdigest(),
            'independent_formal_approval': False, 'semantic_correctness_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--response', type=Path, required=True)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    args = parser.parse_args()
    require(1 <= args.start <= args.end <= 48, 'invalid range')
    print(json.dumps(verify(args.packet, args.response, args.events, args.start, args.end), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
