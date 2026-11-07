"""Replay source bindings, observed presentation, citations and staged seals.

This verifies archived artifacts, not semantic truth, independence, or collection permission.
"""
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/review/2026-11-07-scope-input-review-v1'
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_explanation_scope_input_review_batch as batch_verifier


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.utcoffset() is not None, 'timestamp lacks timezone')
    return parsed


def visible_items(path, source):
    found = set()
    for line in path.read_text().splitlines():
        event = json.loads(line)
        item = event.get('item', {})
        if event.get('type') != 'item.completed' or item.get('type') != 'command_execution':
            continue
        for output_line in item.get('aggregated_output', '').splitlines():
            try:
                data = json.loads(output_line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get('item_id') in source:
                require(data == source[data['item_id']], 'displayed item differs')
                found.add(data['item_id'])
    require(found == set(source), 'not all source items visibly presented')


def main():
    inp, focal, coord, audit = (ARCHIVE / name for name in ('input', 'focal', 'coordinator', 'process-audit'))
    source = load(ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2/input-packet.json')
    packet = load(inp / 'input_packet.json')
    require(set(packet) == {'items'} and packet['items'] == source['items'] and len(packet['items']) == 48,
            'anonymous input differs from source')
    require(all(set(x) == {'item_id', 'question', 'documents'} for x in packet['items']), 'unexpected input metadata')
    audit_response = load(inp / 'audit2-response.txt')
    require(all(x == 'absent' for x in audit_response['exposure_categories'].values())
            and len(audit_response['exposure_categories']) == 5, 'candidate exposure self-report differs')
    delivery = load(coord / 'phase1_delivery.json')
    for name in ('input_packet.json', 'review_template.json', 'phase1_task.txt'):
        require(delivery['files'][name] == sha(inp / name), 'input delivery artifact changed')
    require(delivery['audit_sha256'] == sha(inp / 'audit2-response.txt'), 'exposure report binding changed')
    seal = load(inp / 'input_seal.json')
    review = load(inp / 'input_review_sealed.json')
    completion = load(inp / 'completion-response.txt')
    require(isinstance(completion['review_completed'], str)
            and completion['review_completed'].startswith('All 48 items received batch assessments.'),
            'reviewer completion declaration differs')
    require(seal['input_review_sha256'] == sha(inp / 'input_review_sealed.json')
            and seal['input_packet_sha256'] == sha(inp / 'input_packet.json')
            and seal['audit_sha256'] == sha(inp / 'audit2-response.txt')
            and seal['completion_declaration_sha256'] == sha(inp / 'completion-response.txt'), 'input seal mismatch')
    require(stamp(delivery['delivered_at']) < stamp(seal['sealed_at']), 'input order differs')
    require(review['reviewer_id'] == 'SCOPECLI20261107R01' and len(review['items']) == 48,
            'review count or reviewer differs')
    reconstructed, quote_count = [], 0
    for b in range(1, 7):
        prefix = f'batch{b:02d}'
        response, events = inp / f'{prefix}-response.txt', inp / f'{prefix}-events.jsonl'
        start, end = (b - 1) * 8 + 1, b * 8
        check = batch_verifier.verify(inp / 'input_packet.json', response, events, start, end)
        require(check == load(inp / f'{prefix}-validation.json'), 'batch verification changed')
        events_data = [json.loads(x) for x in events.read_text().splitlines()]
        threads = [x['thread_id'] for x in events_data if x.get('type') == 'thread.started']
        require(threads == [review['thread_id']], 'batch reviewer session differs')
        descriptor = review['batches'][b - 1]
        require(descriptor['response_sha256'] == sha(response) and descriptor['events_sha256'] == sha(events)
                and descriptor['task_sha256'] == sha(inp / f'{prefix}-task.txt'), 'batch binding differs')
        reconstructed.extend(load(response)['items'])
        quote_count += check['exact_quote_occurrences']
    require(reconstructed == review['items'] and quote_count == 252, 'review aggregate differs')

    offset_artifact = load(coord / 'input_citation_offsets.json')
    require(offset_artifact['input_packet_sha256'] == sha(inp / 'input_packet.json')
            and offset_artifact['sealed_review_sha256'] == sha(inp / 'input_review_sealed.json'), 'offset binding differs')
    inputs = {x['item_id']: x for x in packet['items']}
    expected_citations = []
    for row in review['items']:
        for i, c in enumerate(row['target_records']):
            expected_citations.append((row['item_id'], f'target_records[{i}]', c))
        for i, group in enumerate(row['conflicts']):
            for j, c in enumerate(group['records']):
                expected_citations.append((row['item_id'], f'conflicts[{i}].records[{j}]', c))
        for i, c in enumerate(row['evidence_citations']):
            expected_citations.append((row['item_id'], f'evidence_citations[{i}]', c))
    require(len(expected_citations) == len(offset_artifact['entries']) == 252, 'offset citation count differs')
    for (item_id, field, citation), entry in zip(expected_citations, offset_artifact['entries']):
        require((entry['item_id'], entry['review_field'], entry['document_index']) ==
                (item_id, field, citation['document_index']), 'offset identifier differs')
        text = inputs[item_id]['documents'][citation['document_index'] - 1]
        quote = citation['quote']
        positions = [[m.start(), m.start() + len(quote)] for m in re.finditer(f'(?={re.escape(quote)})', text)]
        require(entry['quote_sha256'] == hashlib.sha256(quote.encode()).hexdigest()
                and entry['unicode_end_exclusive_occurrences'] == positions and positions, 'offset mismatch')

    mapping_source = ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2/coordinator.json'
    table_source = ROOT / 'docs/review/2026-11-07-explanation-scope-audit/item-structure.csv'
    item_mapping = load(mapping_source)['mapping']
    with table_source.open() as stream:
        table = {x['item_id']: x for x in csv.DictReader(stream)}
    comparison = load(coord / 'post_seal_comparison.json')
    value_comparison = load(coord / 'post_seal_target_values.json')
    require(comparison['sealed_input_sha256'] == sha(inp / 'input_review_sealed.json')
            and comparison['seal_sha256'] == sha(inp / 'input_seal.json')
            and comparison['coordinator_mapping_source_sha256'] == sha(mapping_source)
            and comparison['structural_table_sha256'] == sha(table_source), 'comparison source differs')
    require(value_comparison['review_sha256'] == sha(inp / 'input_review_sealed.json')
            and value_comparison['seal_sha256'] == sha(inp / 'input_seal.json')
            and value_comparison['mapping_sha256'] == sha(mapping_source)
            and value_comparison['structural_table_sha256'] == sha(table_source), 'value comparison source differs')
    expected_state = {'S': 'target_record_supported', 'I0': 'no_target_record',
                      'IU': 'no_target_record', 'CT': 'conflicting_target_records'}
    compared = {x['review_id']: x for x in comparison['rows']}
    compared_values = {x['review_id']: x for x in value_comparison['rows']}
    require(len(compared) == len(compared_values) == len(review['items']) == 48, 'comparison inventory differs')
    for row in review['items']:
        item = item_mapping[row['item_id']]
        condition = item.rsplit('_', 1)[1]
        scope = []
        for conflict in row['conflicts']:
            entity = re.search(r'XU-\d+', conflict['entity'])
            field = re.search(r'\b(alpha|omega)\b', conflict['field'], re.I)
            scope.append(f'{entity.group(0)}.{field.group(1).lower()}' if entity and field else 'unparsed')
        actual_scope = '|'.join(sorted(scope)) if scope else 'none'
        expected_scope = table[item]['conflict_scope']
        expected = {'review_id': row['item_id'], 'source_item_id': item, 'condition': condition,
                    'reviewer_target_record_state': row['target_record_state'],
                    'construction_expected_state': expected_state[condition],
                    'state_agrees': row['target_record_state'] == expected_state[condition],
                    'reviewer_conflict_scope_normalized': actual_scope, 'construction_conflict_scope': expected_scope,
                    'conflict_scope_agrees': actual_scope == expected_scope}
        require(compared[row['item_id']] == expected, 'state or conflict comparison differs')
        actual_values = sorted({x['value'] for x in row['target_records']})
        expected_values = sorted(set(table[item]['target_values'].split('|')) - {''})
        require(compared_values[row['item_id']] == {
            'review_id': row['item_id'], 'source_item_id': item, 'reviewer_target_values': actual_values,
            'construction_target_values': expected_values, 'agrees': actual_values == expected_values},
            'target value comparison differs')
    require(comparison['state_agreements'] == sum(x['state_agrees'] for x in compared.values())
            and comparison['conflict_scope_agreements'] == sum(x['conflict_scope_agrees'] for x in compared.values())
            and value_comparison['agreed'] == sum(x['agrees'] for x in compared_values.values()),
            'comparison summary differs')

    focal_packet = load(focal / 'phase2_focal_packet.json')
    focal_response = load(focal / 'phase2_focal_response.txt')
    focal_seal = load(focal / 'phase2_focal_seal.json')
    focal_delivery = load(coord / 'phase2_focal_delivery.json')
    require(stamp(seal['sealed_at']) < stamp(focal_delivery['delivered_at']) < stamp(focal_seal['sealed_at']),
            'focal case timing differs')
    require(focal_seal['focal_packet_sha256'] == sha(focal / 'phase2_focal_packet.json')
            and focal_seal['focal_response_sha256'] == sha(focal / 'phase2_focal_response.txt')
            and focal_seal['focal_events_sha256'] == sha(focal / 'phase2_focal_events.jsonl')
            and focal_seal['input_seal_sha256'] == sha(inp / 'input_seal.json')
            and focal_seal['delivery_sha256'] == sha(coord / 'phase2_focal_delivery.json'), 'focal binding differs')
    fi = {x['item_id']: x for x in focal_packet['items']}
    mapping = load(coord / 'phase2_focal_mapping.json')
    old_input = {x['item_id']: x for x in load(ROOT / 'docs/review/2026-10-23-semantic-claims-v1/public/input_packet.json')['items']}
    old_output = {x['item_id']: x for x in load(ROOT / 'docs/review/2026-10-23-semantic-claims-v1/public/output_packet.json')['items']}
    require(set(fi) == set(mapping) == {'F001', 'F002', 'F003'}, 'focal inventory differs')
    for anonymous, original in mapping.items():
        require(fi[anonymous] == {'item_id': anonymous, 'question': old_input[original]['question'],
                                  'documents': old_input[original]['documents'], 'answer': old_output[original]['answer']},
                'focal source differs')
    visible_items(focal / 'phase2_focal_events.jsonl', fi)
    require(focal_response['packet_sha256'] == sha(focal / 'phase2_focal_packet.json')
            and {x['item_id'] for x in focal_response['items']} == set(fi), 'focal response mismatch')
    focal_quotes = 0
    for row in focal_response['items']:
        item = fi[row['item_id']]
        for q in row['answer_quotes']:
            require(q in item['answer'], 'focal answer quote missing')
            focal_quotes += 1
        for c in row['document_citations']:
            require(type(c['document_index']) is int and 1 <= c['document_index'] <= 5
                    and c['quote'] in item['documents'][c['document_index'] - 1], 'focal document quote missing')
            focal_quotes += 1
    require(focal_quotes == focal_seal['exact_quote_occurrences'] == 16, 'focal quote count differs')

    focal_comparison = load(coord / 'post_seal_focal_comparison.json')
    prior_path = ROOT / 'docs/review/2026-11-06-informed-followup/informed-adjudication.json'
    old_cli_path = ROOT / 'docs/review/2026-11-06-isolated-cli-review-v1/coordinator/focal_cases.json'
    require(focal_comparison['new_review_sha256'] == sha(focal / 'phase2_focal_response.txt')
            and focal_comparison['new_review_seal_sha256'] == sha(focal / 'phase2_focal_seal.json')
            and focal_comparison['mapping_sha256'] == sha(coord / 'phase2_focal_mapping.json')
            and focal_comparison['prior_informed_sha256'] == sha(prior_path)
            and focal_comparison['prior_cli_focal_sha256'] == sha(old_cli_path), 'focal comparison source differs')
    prior = {x['item_id']: x for x in load(prior_path)['focal_scope_judgments']}
    old_cli = {x['item_id']: x for x in load(old_cli_path)['cases']}
    focal_rows = {x['review_id']: x for x in focal_comparison['rows']}
    require(set(focal_rows) == set(fi), 'focal comparison inventory differs')
    for row in focal_response['items']:
        item = mapping[row['item_id']]
        wanted = {'review_id': row['item_id'], 'old_item_id': item,
                  'new_reviewer_withholds_with_support': row['withholds_with_support'],
                  'new_reviewer_target_conflict_assertion': row['target_conflict_assertion'],
                  'new_reviewer_broader_conflict_support': row['broader_conflict_support'],
                  'prior_informed_target_conflict': prior[item]['narrow_target_conflict'],
                  'prior_informed_reason': prior[item]['reason'],
                  'prior_cli_broader_conflict_atom_judgment': old_cli[item]['reviewer_conflict_atom']['judgment'],
                  'same_narrow_scope_judgment': row['target_conflict_assertion'] == prior[item]['narrow_target_conflict']}
        require(focal_rows[row['item_id']] == wanted, 'focal comparison differs')
    require(focal_comparison['same_narrow_judgment_count'] ==
            sum(x['same_narrow_scope_judgment'] for x in focal_rows.values()), 'focal comparison count differs')

    process_delivery = load(coord / 'phase3_audit_delivery.json')
    process_seal = load(audit / 'phase3_audit_initial_seal.json')
    supplement_seal = load(audit / 'phase3_audit_supplement_seal.json')
    process_result = load(audit / 'phase3_audit_response.txt')
    supplement = load(audit / 'phase3_audit_supplement_response.txt')
    require(stamp(focal_seal['sealed_at']) < stamp(process_delivery['delivered_at']) < stamp(process_seal['sealed_at'])
            < stamp(supplement_seal['sealed_at']), 'process-audit chronology differs')
    for details in process_delivery['files'].values():
        require(sha(ROOT / details['source']) == details['sha256'], 'process evidence source differs')
    require(process_seal['response_sha256'] == sha(audit / 'phase3_audit_response.txt')
            and process_seal['events_sha256'] == sha(audit / 'phase3_audit_events.jsonl')
            and process_seal['evidence_delivery_sha256'] == sha(coord / 'phase3_audit_delivery.json'),
            'process audit binding differs')
    require(supplement_seal['supplement_response_sha256'] == sha(audit / 'phase3_audit_supplement_response.txt')
            and supplement_seal['supplement_events_sha256'] == sha(audit / 'phase3_audit_supplement_events.jsonl')
            and supplement_seal['initial_audit_seal_sha256'] == sha(audit / 'phase3_audit_initial_seal.json'),
            'process audit supplement binding differs')
    require(process_result['formal_independent_approval'] is False and len(process_result['findings']) == 7
            and supplement['formal_independent_approval'] is False, 'formal approval or finding count differs')
    old_cmd = load(ROOT / 'docs/review/2026-11-07-explanation-scope-audit/cli-visible-commands.json')
    names = {'phase1/trace.json': 'input_trace.json', 'phase2-initial/trace.json': 'answer_trace.json',
             'phase2/trace.json': 'metadata_trace.json'}
    first = {(names[x['trace']], x['id']): (x['exit_code'], x['command_sha256']) for x in old_cmd['commands']}
    second = {(x['trace'], x['item_id']): (x['exit_code'], x['command_sha256'])
              for x in supplement['scope']['command_inventory']}
    require(len(first) == len(second) == 31 and first == second, 'supplement command inventory differs')

    candidate_commands = load(coord / 'candidate_visible_commands.json')
    for name, digest in candidate_commands['event_file_sha256'].items():
        require(sha(ARCHIVE / name) == digest, 'candidate event source differs')
    commands = []
    for name in sorted(candidate_commands['event_file_sha256']):
        for line in (ARCHIVE / name).read_text().splitlines():
            event = json.loads(line)
            item = event.get('item', {})
            if event.get('type') == 'item.completed' and item.get('type') == 'command_execution':
                commands.append((name, item.get('id'), item.get('exit_code'),
                                 hashlib.sha256(item.get('command', '').encode()).hexdigest()))
    recorded = [(x['event_file'], x['item_id'], x['exit_code'], x['command_sha256'])
                for x in candidate_commands['events']]
    require(commands == recorded and len(commands) == 19, 'candidate visible command inventory differs')

    follow = ARCHIVE / 'scope-followup'
    follow_result = load(follow / 'phase4_scope_reconsideration_response.txt')
    follow_seal = load(follow / 'phase4_scope_reconsideration_seal.json')
    require(follow_seal['task_sha256'] == sha(follow / 'phase4_scope_reconsideration_task.txt')
            and follow_seal['response_sha256'] == sha(follow / 'phase4_scope_reconsideration_response.txt')
            and follow_seal['events_sha256'] == sha(follow / 'phase4_scope_reconsideration_events.jsonl')
            and follow_seal['prior_focal_seal_sha256'] == sha(focal / 'phase2_focal_seal.json')
            and follow_seal['case_packet_sha256'] == sha(focal / 'phase2_focal_packet.json'),
            'informed follow-up binding differs')
    require(stamp(supplement_seal['sealed_at']) < stamp(follow_seal['recorded_at']),
            'informed follow-up record time differs')
    follow_events = [json.loads(x) for x in (follow / 'phase4_scope_reconsideration_events.jsonl').read_text().splitlines()]
    require([x['thread_id'] for x in follow_events if x.get('type') == 'thread.started'] == [review['thread_id']],
            'informed follow-up reviewer differs')
    require(follow_result['reviewer_id'] == review['reviewer_id']
            and follow_result['stage'] == 'informed_followup_after_prior_judgment_disclosure'
            and follow_result['original_f003_judgment_preserved'] is True
            and follow_result['criterion_A'] == follow_seal['followup_criterion_A']
            and follow_result['criterion_B'] == follow_seal['followup_criterion_B']
            and follow_result['answer_quote'] in fi['F003']['answer']
            and follow_seal['formal_independent_approval'] is False,
            'informed follow-up does not match preserved source')

    manifest_path = ARCHIVE / 'artifact_manifest.json'
    require(manifest_path.is_file(), 'archive manifest missing')
    manifest = load(manifest_path)
    records = {x['path']: x for x in manifest['files']}
    actual_files = {str(x.relative_to(ARCHIVE)) for x in ARCHIVE.rglob('*')
                    if x.is_file() and x != manifest_path}
    require(len(records) == manifest['file_count'] and set(records) == actual_files,
            'archive manifest file inventory differs')
    for name, entry in records.items():
        path = ARCHIVE / name
        require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'],
                'archive artifact fingerprint differs')

    print(json.dumps({'status': 'source_bindings_citations_visible_text_and_stage_order_verified_not_semantics_or_independence',
                      'reviewer_sessions': 1, 'input_items_reviewed': 48, 'input_quotes': quote_count,
                      'target_state_agreements': comparison['state_agreements'],
                      'target_value_agreements': value_comparison['agreed'],
                      'conflict_scope_agreements': comparison['conflict_scope_agreements'],
                      'focal_cases_reviewed': 3, 'focal_quotes': focal_quotes, 'old_cli_command_inventory': 31,
                      'state_counts': dict(Counter(x['target_record_state'] for x in review['items'])),
                      'focal_target_conflict_assertion': {mapping[x['item_id']]: x['target_conflict_assertion']
                                                           for x in focal_response['items']},
                      'q052_informed_followup': {'criterion_A': follow_result['criterion_A'],
                                                  'criterion_B': follow_result['criterion_B']},
                      'semantic_truth_verified': False, 'formal_independent_approval': False,
                      'formal_gate': False, 'gpu_launch_ready': False, 'new_experimental_answers': 0},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
