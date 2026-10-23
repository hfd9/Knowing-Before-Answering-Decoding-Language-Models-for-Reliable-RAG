"""Independently check the saved 55-item review package without importing its builder."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-10-23-semantic-claims-v1'


def read(path):
    return json.loads(path.read_text())


def check(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = read(BASE/'manifest.json')
    for name, expected in {**manifest['source_sha256'], **manifest['payload_sha256']}.items():
        check(sha(ROOT/name) == expected, 'File hash mismatch: '+name)
    inputs = read(BASE/'public/input_packet.json')['items']
    outputs = read(BASE/'public/output_packet.json')['items']
    cases = read(BASE/'coordinator/cases.json')['cases']
    check(len(inputs) == len(outputs) == len(cases) == 55, 'Wrong size')
    ids = [f'Q{i:03d}' for i in range(1,56)]
    check([r['item_id'] for r in inputs] == [r['item_id'] for r in outputs] ==
          [r['item_id'] for r in cases] == ids, 'ID join mismatch')
    check(all(set(r) == {'item_id','question','documents'} for r in inputs), 'Reviewer input field leak')
    check(all(set(r) == {'item_id','answer','candidate_sentence_units'} for r in outputs), 'Output field leak')
    audit = read(ROOT/'docs/records/2026-10-21-insufficient-answer-audit.json')['cases']
    anchor_ids = {r['id'] for r in audit}
    rows = list(csv.DictReader((ROOT/'docs/records/2026-10-21-semantic-transfer-exploratory-behavior-cells.csv').open()))
    bases = {r['original_id'] for r in rows if r['id'] in anchor_ids}
    expected_old = {r['id'] for r in rows if r['original_id'] in bases and r['condition'] in ['I','S']}
    check(len(bases) == 13 and len(expected_old) == 52, 'Original selection mismatch')
    check({r['source_id'] for r in cases if r['source_family']=='old'} == expected_old, 'Old packet selection mismatch')
    check({r['source_id'] for r in cases if r['source_family']=='relation'} ==
          {'rel05_TA_v2','rel03_OQ_v2','rel03_OA_v1'}, 'Explanation selection mismatch')
    check(dict(Counter(r['primary_pattern'] for r in audit)) ==
          dict(fact_reassignment=8, unsupported_relation_promotion=9, absent_answer_value=6), 'Old taxonomy changed')
    check({r['source_id'] for r in cases if r['selection_group']=='same_base_I_nonanswer_control'} ==
          {'stv04_B_I','stv19_B_I','stv24_A_I'}, 'Related nonanswer set mismatch')
    check({r['source_id'] for r in cases if r['selection_group']=='old_23_answer_anchors'} == anchor_ids,
          'Anchor role mismatch')
    source_data = {}
    for family, directory in [('old','qwen2.5-3b-semantic-transfer-exploratory-v5-v1'),
                              ('relation','qwen2.5-3b-relation-attachment-v1')]:
        run = ROOT/'runs'/directory
        source_data[family] = (
            {r['item_id']:r for r in read(run/'behavior_review/packet.json')['items']},
            read(run/'coordinator/behavior_mapping.json'),
            {r['id']:r for r in read(run/'predictions.json')['records']})
    unit_count = citation_count = 0
    for inp, out, case in zip(inputs, outputs, cases):
        packet, mapping, predictions = source_data[case['source_family']]
        original = packet[mapping[case['source_id']]]
        check(inp['question'] == original['question'] and inp['documents'] == original['documents']
              and len(inp['documents']) == 5, 'Unedited input mismatch')
        check(out['answer'] == original['answer'] == predictions[case['source_id']]['raw_output'] ==
              case['full_answer'], 'Unedited output mismatch')
        answer = out['answer']
        end = 0
        check(case['candidate_sentence_units'] == out['candidate_sentence_units'], 'Sentence list mismatch')
        for u in out['candidate_sentence_units']:
            check(u['start'] == end and u['end'] > u['start'], 'Sentence gap/overlap')
            check(answer[u['start']:u['end']] == u['quote'] and
                  u['text_sha256'] == hashlib.sha256(answer.encode()).hexdigest(), 'Sentence reference mismatch')
            end = u['end']; unit_count += 1
        check(end == len(answer), 'Answer not fully covered')
        focal = case['focal_prior_author_audit']['output_reference']
        check(answer[focal['start']:focal['end']] == focal['quote'] and
              focal['text_sha256'] == hashlib.sha256(answer.encode()).hexdigest(), 'Focal claim mismatch')
        for ref in case['prior_document_context_references']:
            doc = inp['documents'][ref['document_index']-1]
            check(doc[ref['start']:ref['end']] == ref['quote'] and
                  hashlib.sha256(doc.encode()).hexdigest() == ref['text_sha256'], 'Document reference mismatch')
            citation_count += 1
    for name, columns in [
        ('input_review_template.json', ['target_interpretation','answerability','candidate_answer',
            'document_support','missing_link','ambiguity','conflicting_propositions']),
        ('claim_review_template.json', ['gives_specific_target_answer','target_claim_supported',
            'withholding_matches_gap','explanation_all_claims_supported','full_answer_claim_coverage_confirmed'])]:
        template = read(BASE/'public'/name)
        check(template['reviewer_id'] is None and [r['item_id'] for r in template['items']] == ids,
              'Reviewer metadata mismatch')
        for row in template['items']:
            check(row['status'] == 'unreviewed' and all(row[c] is None for c in columns), 'Nonblank item score')
            if 'claim_reviews' in row:
                out = outputs[ids.index(row['item_id'])]
                check([v['source_span'] for v in row['claim_reviews']] == out['candidate_sentence_units'],
                      'Template unit coverage mismatch')
                check(all(v[k] is None for v in row['claim_reviews'] for k in
                      ['atomic_claims','document_support','counterevidence','missing_link','ambiguity','judgment']),
                      'Nonblank claim score')
        if name.startswith('claim'):
            check(template['sealed_input_review_sha256'] is None and
                  template['sealed_input_review_completed_at'] is None, 'Fabricated input review seal')
    check(all(v is None for v in read(BASE/'public/reviewer_context_template.json').values()),
          'Fabricated reviewer independence audit')
    for phase, expected in [
        ('inputs', {'INSTRUCTIONS.md','input_packet.json','input_packet.md',
                    'input_review_template.json','reviewer_context_template.json'}),
        ('outputs', {'INSTRUCTIONS.md','output_packet.json','output_packet.md','claim_review_template.json'})]:
        with zipfile.ZipFile(BASE/('reviewer-'+phase+'.zip')) as bundle:
            check(set(bundle.namelist()) == expected, 'Unexpected ZIP member or coordinator leakage')
            for name in bundle.namelist():
                check(bundle.read(name) == (BASE/'public'/name).read_bytes(), 'ZIP content mismatch')
    pairs = read(BASE/'coordinator/pairs.json')['pairs']
    expected_pairs = {(r['id'],r['id'][:-1]+'S') for r in rows if r['id'] in expected_old and r['condition']=='I'}
    check({(p['source_I_id'],p['source_S_id']) for p in pairs} == expected_pairs and len(pairs)==26,
          'I/S pair mismatch')
    inventory = read(BASE/'coordinator/document_inventory.json')
    expected_slots = [dict(item_id=r['item_id'],document_index=i,sha256=hashlib.sha256(d.encode()).hexdigest())
                      for r in inputs for i,d in enumerate(r['documents'],1)]
    check(inventory['slots'] == expected_slots and len(expected_slots)==275, 'Document inventory mismatch')
    table = list(csv.DictReader((BASE/'coordinator/four_axes.csv').open()))
    check(len(table)==55 and {r['item_id'] for r in table}==set(ids), 'Four-axis table coverage mismatch')
    for row, case in zip(table,cases):
        focal=case['focal_prior_author_audit']
        check(row['source_id']==case['source_id'] and row['claim']==focal['claim'] and
              row['missing_link']==focal['missing_link'] and row['ambiguity']==focal['ambiguity'] and
              row['prior_author_assessment']==focal['assessment'] and
              json.loads(row['document_support_context'])==case['prior_document_context_references'],
              'Four-axis table content mismatch')
    seal=read(ROOT/'docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json')
    check(all(sha(ROOT/p)==h for p,h in seal['files'].items()), 'Original fit artifact changed')
    check(all(v is None for v in read(ROOT/'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/approved_labels.json').values()),
          'Formal labels changed')
    report = dict(status='material_integrity_verified_not_semantic_approval', verifier_sha256=sha(Path(__file__)),
        manifest_sha256=sha(BASE/'manifest.json'), source_files=len(manifest['source_sha256']),
        payload_files=len(manifest['payload_sha256']), items=55, old_bases=13, old_I_S_pairs=26,
        document_slots=275, unique_document_texts=len({r['sha256'] for r in expected_slots}),
        sentence_candidate_units=unit_count, document_context_citations=citation_count,
        independent_semantic_reviews=0, new_semantic_scores=0, new_model_calls=0, new_fits=0,
        fit_sealed_files_unchanged=len(seal['files']), remaining_original_design_fits=0,
        held_out_380_accessed=False, formal_labels_added=0,
        checks=['source and payload SHA256', 'selection and complete pairs', 'raw question/documents/answer joins',
                'full sentence span coverage and references', '55 four-axis table rows', 'all review fields blank',
                'no fabricated reviewer or input seal', 'ZIP contents and stage separation',
                '275 document slots', 'original fit seal and null formal labels'])
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
