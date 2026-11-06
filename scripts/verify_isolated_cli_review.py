"""Read-only replay of saved CLI review artifacts, citations and presented text.

This verifies records and arithmetic, not semantic truth or reviewer independence.
"""
import ast
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-11-06-isolated-cli-review-v1'
SOURCE = ROOT / 'docs/review/2026-10-23-semantic-claims-v1/public'
RECORD = ROOT / 'docs/records/2026-11-06-isolated-cli-review.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(ok, message):
    if not ok:
        raise ValueError(message)


def citation(ref, text):
    start, end = ref['start'], ref['end']
    check(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Citation range')
    check(text[start:end] == ref['quote'], 'Citation text')
    if 'text_sha256' in ref:
        check(ref['text_sha256'] == hashlib.sha256(text.encode()).hexdigest(), 'Citation hash')


def document_citation(ref, documents):
    slot = ref['document_index']
    check(type(slot) is int and 1 <= slot <= len(documents), 'Document citation slot')
    citation(ref, documents[slot - 1])


def main():
    record = read(RECORD)
    for group in ['source_sha256', 'artifact_sha256']:
        for name, expected in record[group].items():
            check(sha(ROOT / name) == expected, 'File hash: ' + name)
    packets = {r['item_id']: r for r in read(SOURCE / 'input_packet.json')['items']}
    answers = {r['item_id']: r for r in read(SOURCE / 'output_packet.json')['items']}
    input_rows = read(BASE / 'phase1/input_review.json')['items']
    form = read(BASE / 'phase2/claim_review.json')
    rows = form['items']
    check(len(input_rows) == len(rows) == 55, 'Review size')
    check({r['item_id'] for r in input_rows} == {r['item_id'] for r in rows} == set(packets), 'Review IDs')
    seal = read(BASE / 'phase1/input_seal.json')
    check(sha(BASE / 'phase1/input_review.json') == seal['input_review_sha256'], 'Input seal')
    check(form['sealed_input_review_sha256'] == seal['input_review_sha256'], 'Output seal binding')
    check(form['sealed_input_review_completed_at'] == seal['sealed_at'], 'Receipt time mapping')
    initial = read(BASE / 'phase2-initial/claim_review.json')
    changed = {k for k in set(initial) | set(form) if initial.get(k) != form.get(k)}
    check(changed == {'sealed_input_review_completed_at'} and initial['items'] == rows,
          'Metadata correction changed review judgments')
    delivery = read(BASE / 'coordinator/delivery_stage2.json')
    context = read(BASE / 'phase2/output_context.json')
    time = datetime.fromisoformat
    check(time(read(BASE / 'phase1/context.json')['reviewed_at']) <= time(seal['sealed_at']) <
          time(delivery['delivered_at']) <= time(context['answer_review_completed_at']), 'Stage order')
    check(delivery['author_results_delivered'] is False and delivery['coordinator_mapping_delivered'] is False,
          'Unexpected material delivery')
    counts = Counter()
    input_citations = output_citations = 0
    for r in input_rows:
        check(r['status'] == 'reviewed', 'Unreviewed input')
        for ref in r['document_support']:
            document_citation(ref, packets[r['item_id']]['documents'])
            input_citations += 1
    for r in rows:
        iid = r['item_id']
        check(r['status'] == 'reviewed' and r['full_answer_claim_coverage_confirmed'] is True, 'Output coverage')
        expected = {u['unit_id']: u for u in answers[iid]['candidate_sentence_units']}
        check(len(r['claim_reviews']) == len(expected), 'Unit count')
        seen = set()
        for unit in r['claim_reviews']:
            check(unit['source_span'] == expected[unit['unit_id']], 'Original source span')
            check(bool(unit['atomic_claims']), 'Empty unit')
            for atom in unit['atomic_claims']:
                check(atom['claim_id'] not in seen, 'Duplicate claim ID')
                seen.add(atom['claim_id'])
                counts[atom['judgment']] += 1
                ref = atom['output_citation']
                citation(ref, answers[iid]['answer'])
                span = unit['source_span']
                check(span['start'] <= ref['start'] < ref['end'] <= span['end'], 'Atom outside unit')
                for kind in ['document_support', 'counterevidence']:
                    for evidence in atom[kind]:
                        document_citation(evidence, packets[iid]['documents'])
                        output_citations += 1
    traces = [read(BASE / name)['events'] for name in
              ['phase1/trace.json', 'phase2-initial/trace.json', 'phase2/trace.json']]
    for events in traces:
        check({e['thread_id'] for e in events if e.get('type') == 'thread.started'} ==
              {record['reviewer_thread_id']}, 'Reviewer session changed')
    first_outputs = [e['item'].get('aggregated_output', '') for e in traces[0]
                     if e.get('item', {}).get('type') == 'command_execution' and
                     e['item'].get('status') == 'completed']
    texts = {t for r in packets.values() for t in r['documents']}
    presented = {t for t in texts if any(t in out for out in first_outputs)}
    for out in first_outputs:
        start = out.find('\n{\n')
        if start < 0:
            continue
        try:
            value = json.loads(out[start + 1:])
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get('documents'), list):
            presented.update(value['documents'])
    check(texts <= presented, 'Input text not fully represented in recorded output')
    check(all(any(r['question'] in out for out in first_outputs) for r in packets.values()), 'Question coverage')
    displayed_units = {}
    for e in traces[1]:
        item = e.get('item', {})
        if item.get('type') != 'command_execution' or item.get('status') != 'completed':
            continue
        current = None
        for line in item.get('aggregated_output', '').splitlines():
            header = re.match(r'^(Q\d{3}) QUESTION:', line)
            if header:
                current = header.group(1)
                continue
            unit = re.match(r'^(U\d{2}) (.+)$', line)
            if current and unit:
                try:
                    value = ast.literal_eval(unit.group(2))
                except (ValueError, SyntaxError):
                    continue
                if isinstance(value, str):
                    displayed_units[current, unit.group(1)] = value
    for iid, r in answers.items():
        check(all(displayed_units.get((iid, u['unit_id'])) == u['quote']
                  for u in r['candidate_sentence_units']), 'Answer text presentation')
        check(''.join(u['quote'] for u in r['candidate_sentence_units']) == r['answer'], 'Answer reconstruction')
    check(len(displayed_units) == 82, 'Displayed unit count')
    report = read(BASE / 'coordinator/intake-snapshot/intake_report.json')
    check((report['reviewed_inputs'], report['reviewed_outputs'], report['reviewed_atomic_claims']) ==
          (55, 55, sum(counts.values())), 'Intake counts')
    check(dict(counts) == report['claim_judgment_counts'] and sum(counts.values()) == 172, 'Claim counts')
    check(report['independent_semantic_approvals'] == 0 and report['formal_gate'] is False and
          report['gpu_launch_ready'] is False, 'No automatic approval')
    comparison = read(BASE / 'coordinator/intake-snapshot/endpoint_comparison.json')['rows']
    summary = read(BASE / 'coordinator/comparison_summary.json')['endpoint_disagreements']
    for field, value in summary.items():
        ids = [r['item_id'] for r in comparison if r[field] is True]
        check(value['item_ids'] == ids and value['count'] == len(ids), 'Endpoint disagreement count')
    raw_rows = {r['item_id']: r for r in rows}
    for case in read(BASE / 'coordinator/focal_cases.json')['cases']:
        row = raw_rows[case['item_id']]
        atom = case['reviewer_conflict_atom']
        check(atom in [a for u in row['claim_reviews'] for a in u['atomic_claims']], 'Focal atom copy')
        check(case['reviewer_gives_target'] == row['gives_specific_target_answer'] and
              case['reviewer_withholding_support'] == row['withholding_matches_gap'] and
              case['reviewer_explanation_support'] == row['explanation_all_claims_supported'], 'Focal endpoints')
    fit = read(ROOT / 'docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json')
    check(len(fit['files']) == 12 and all(sha(ROOT / p) == h for p, h in fit['files'].items()), 'Fit seal')
    local = ROOT / record['intake_run']
    local_files = 0
    if local.exists():
        for path in (BASE / 'coordinator/intake-snapshot').glob('*.json'):
            check(sha(path) == sha(local / path.name), 'Local/archive intake mismatch')
            local_files += 1
    print(json.dumps(dict(status='records_references_and_text_presentation_verified_not_semantic_certification',
        protected_source_files=len(record['source_sha256']), archived_artifacts=len(record['artifact_sha256']),
        reviewed_inputs=55, reviewed_outputs=55, claim_instances=sum(counts.values()), claim_counts=dict(counts),
        input_citations=input_citations, output_document_citations=output_citations,
        presented_questions=55, presented_unique_documents=len(texts), presented_answer_units=len(displayed_units),
        metadata_changed_fields=sorted(changed), fit_sealed_files_unchanged=12,
        local_intake_files_matching_archive=local_files, independent_semantic_approvals=0,
        formal_gate=False, gpu_launch_ready=False, new_experimental_model_calls=0, new_fits=0,
        semantic_comprehension_or_independence_proved=False), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
