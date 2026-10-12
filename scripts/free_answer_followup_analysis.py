"""Reproduce the 2026-10-11 same-assistant follow-up; never changes model inputs.

This is a diagnostic review, not a second independent annotator. Frozen v2 labels
remain the source, and all field changes are exported separately before import.
"""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import free_answer_review as review

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/qwen2.5-3b-free-answer-study'
OUT = RUN / 'review/followup-2026-10-11'
CORE = [218, 127, 369, 451, 422, 440, 575, 222,
        216, 232, 76, 465, 573, 594, 56, 466, 306, 528, 349, 487]
SUFFICIENT_UNKNOWN = [170, 298, 44, 269, 348, 538, 509, 467, 162, 238,
                      51, 138, 252, 128, 435, 585, 241, 132, 361]
UNGROUNDED = {
    218: 'No Gettysburg or requested casualty/turning-point comparison in the five documents.',
    369: 'No Chocolat, Joanne or Harris in the five documents; answer lacks documentary grounding.',
    222: 'No ocho or octo in the five documents; quoted octo passage is absent.',
    216: 'No Gettysburg Address, Lincoln or quoted Four score speech in the five documents.',
    306: 'Doves described, but no Dodos evidence; joint genre conclusion lacks its second premise.',
    349: 'No Snowmen reference in the five documents; Time of the Doctor is a different episode.',
    44: 'Grenadine description gives flavor/color, not a nutmeg-free ingredient list; negative claim unsupported.',
    51: 'Grenadine description gives flavor/color, not a nutmeg-free ingredient list; negative claim unsupported.',
    138: 'Film excerpt names IBM News Pad; no HAL 9000 support in the five documents.',
    509: 'Chimaera only listed as a dragon type; supplied truncated article lacks the requested anatomy.',
    252: 'Chimaera only listed as a dragon type; supplied truncated article lacks the requested anatomy.',
    162: 'No target-album linkage in Kinks excerpt or other documents; Kinks attribution unsupported.',
    238: 'Supplied dictionary and hatchment pages give no hawk-chick or eyas naming evidence.',
    361: 'Supplied documents give no basis for the special young-bird name hawk.',
}
MARKERS = [r'original conflict document', r'conflict answer',
           r'here.{0,12}(?:updated|modified|rewritten).{0,12}document',
           r'(?:modify|rewrite|change).{0,35}(?:document|answer)',
           r'modified document', r'rewritten document']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    source = RUN / 'review/annotations_codex_semantic_v2.csv'
    assert digest(source) == 'b09dcfb77f8d2497d91090f495dfa1d6f59447d2441c2886e9eb9eba154483e9'
    manifest_path = RUN / 'review/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest_hash = digest(manifest_path)
    assert manifest_hash == '777016f545c8c23ea7174fb25039aae52fa7988caec9726e3ab9c82bec9274d0'
    rows = list(csv.DictReader(source.open()))
    fields = list(rows[0])
    assert len(rows) == len({r['item_id'] for r in rows}) == 600
    priority = set(CORE + SUFFICIENT_UNKNOWN + [370, 377])
    priority.update(int(r['item_id'].split('_')[1]) for r in rows
                    if r['selects_single_answer'] == 'unknown' or r['acknowledges_conflict'] == 'unknown')
    changes, decisions = [], []
    for row in rows:
        n = int(row['item_id'].split('_')[1])
        if n not in priority:
            continue
        reason = 'Re-read full output and prior notes; ambiguity retained rather than imposing a final-answer rule after observation.'
        updates = {}
        if n in CORE:
            reason = 'Concrete answer or categorical negative remains visible despite disclaimers; substantive-answer yes confirmed.'
        if n in UNGROUNDED:
            updates['answer_correct'] = 'no'
            reason = UNGROUNDED[n]
        if n in [370, 377]:
            updates = {f: 'no' for f in ['has_substantive_answer', 'selects_single_answer', 'answer_correct']}
            reason = ('Initial No is followed by a claim about missing evidence, not a factual denial of the joint property; '
                      '370 explicitly cannot conclude Vachss is a poet; 377 says documents do not provide Seohyun information. '
                      'Context-only single-entity statement does not answer the joint question. Same-assistant judgment; independent review still needed.')
        for field, new in updates.items():
            old = row[field]
            if old != new:
                changes.append(dict(item_id=row['item_id'], field=field, old=old, new=new, reason=reason))
                row[field] = new
        row['reviewer'] = 'Codex-same-assistant-followup-v3'
        row['notes'] += ' Follow-up 2026-10-11: ' + reason
        decisions.append(dict(item_id=row['item_id'], core_case=n in CORE,
                              reason=reason, **{f: row[f] for f in review.FIELDS}))
    v3 = OUT / 'annotations_codex_semantic_v3.csv'
    write_csv(v3, rows, fields)
    write_csv(OUT / 'annotation_changes.csv', changes, ['item_id', 'field', 'old', 'new', 'reason'])
    write_csv(OUT / 'priority_decisions.csv', decisions, ['item_id', 'core_case', 'reason', *review.FIELDS])
    uncertain = [r for r in rows if any(r[f] == 'unknown' for f in review.FIELDS)]
    write_csv(OUT / 'uncertain_items_semantic_v3.csv', uncertain, fields)
    parsed = review.load_annotations(v3, manifest['items'], manifest_hash)
    assert len(parsed) == 600
    joined = json.loads((RUN / 'reports/joined_records.json').read_text())
    # Lookup uses format and instance ID, never CSV position or output text.
    for r in joined:
        r['behavior'] = parsed[(r['format'], r['id'])]
    tickets = {m['item_id']: (m['format'], m['id']) for m in manifest['items']}
    joined_lookup = {(r['format'], r['id']): r for r in joined}
    core_rows = []
    for n in CORE:
        ticket = f'item_{n:04d}'
        r = joined_lookup[tickets[ticket]]
        assert r['true_mode'] == r['probe_pred'] == 'refuse'
        assert r['behavior']['has_substantive_answer'] is True
        core_rows.append(dict(item_id=ticket, format=r['format'], id=r['id'],
                              original_id=r['original_id'], true_mode=r['true_mode'],
                              probe_pred=r['probe_pred'], raw_output=r['raw_output'],
                              raw_output_sha256=hashlib.sha256(r['raw_output'].encode()).hexdigest(),
                              answer_correct=r['behavior']['answer_correct'], notes=r['behavior']['notes']))
    write_csv(OUT / 'core_insufficient_answer_cases.csv', core_rows,
              ['item_id', 'format', 'id', 'original_id', 'true_mode', 'probe_pred',
               'raw_output', 'raw_output_sha256', 'answer_correct', 'notes'])
    quality_rows = list(csv.DictReader((OUT / 'conflict_evidence_quality.csv').open()))
    quality = {r['id']: r['quality'] for r in quality_rows}
    test_rows = [json.loads(line) for line in (ROOT / 'runs/qwen2.5-3b-small/data/instances_test.jsonl').read_text().splitlines()]
    expected = {r['id'] for r in test_rows if r['true_mode'] == 'conflict'}
    assert len(quality) == len(quality_rows) == 100 and set(quality) == expected
    for r in test_rows:
        if r['id'] in quality:
            q = next(x for x in quality_rows if x['id'] == r['id'])
            assert q['documents_sha256'] == hashlib.sha256(json.dumps(r['docs'], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    strata = {}
    for fmt in ['plain', 'chat']:
        strata[fmt] = {}
        for group in sorted(set(quality.values())):
            subset = [r for r in joined if r['format'] == fmt and quality.get(r['id']) == group]
            assert len(subset) == Counter(quality.values())[group]
            strata[fmt][group] = {field: review.rate_bounds(subset, lambda r: True, field)
                                  for field in ['has_substantive_answer', 'acknowledges_conflict', 'selects_single_answer']}
            strata[fmt][group]['probe_conflict_then_select'] = review.rate_bounds(
                subset, lambda r: r['probe_pred'] == 'conflict', 'selects_single_answer')
    metadata = []
    metadata_counts = {}
    for split, expected_n in [('train', 600), ('val', 285), ('test', 300)]:
        data = [json.loads(s) for s in (ROOT / f'runs/qwen2.5-3b-small/data/instances_{split}.jsonl').read_text().splitlines()]
        assert len(data) == expected_n
        for r in data:
            for i, doc in enumerate(r['docs'], 1):
                for pattern in MARKERS:
                    match = re.search(pattern, doc, re.I)
                    if match:
                        metadata.append(dict(split=split, id=r['id'], true_mode=r['true_mode'],
                                             document_index=i, pattern=pattern,
                                             excerpt=doc[max(0, match.start()-35):match.end()+80].replace('\n', ' ')))
        ids = {r['id'] for r in metadata if r['split'] == split}
        metadata_counts[split] = dict(total_instances=expected_n, flagged_instances=len(ids),
                                      by_class=dict(Counter(r['true_mode'] for r in data if r['id'] in ids)))
    write_csv(OUT / 'editing_metadata_flags.csv', metadata, ['split', 'id', 'true_mode', 'document_index', 'pattern', 'excerpt'])
    # Existing page contains only public questions/docs/outputs. Separate browser
    # storage prevents another annotator inheriting this assistant's ratings.
    blind_dir = OUT / 'independent_review'; blind_dir.mkdir(exist_ok=True)
    page = (RUN / 'review/blind_review.html').read_text()
    old_key = "const key='kba-review-'+manifestHash;"
    assert old_key in page
    (blind_dir / 'blind_review.html').write_text(page.replace(old_key, "const key='kba-independent-review-20261011-'+manifestHash;"))
    (blind_dir / 'annotations_template.csv').write_bytes((RUN / 'review/annotations_template.csv').read_bytes())
    template = list(csv.DictReader((blind_dir / 'annotations_template.csv').open()))
    assert len(template) == 600 and all(r[f] == 'unknown' for r in template for f in review.FIELDS)
    summary = dict(review_type='same_assistant_followup_not_independent',
                   source_sha256=digest(source), annotations_v3_sha256=digest(v3), manifest_sha256=manifest_hash,
                   reviewed_priority_rows=len(priority), core_cases_confirmed=len(CORE),
                   changed_fields=len(changes), changed_rows=len({r['item_id'] for r in changes}),
                   five_fields_known=600-len(uncertain), at_least_one_unknown=len(uncertain),
                   quality_counts=dict(Counter(quality.values())), conflict_strata=strata,
                   editing_marker_patterns=MARKERS, editing_marker_counts=metadata_counts,
                   field_counts={f: dict(Counter(r[f] for r in rows)) for f in review.FIELDS},
                   independent_review='blank pack prepared; no independent annotations or agreement score')
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ['conflict_strata', 'field_counts', 'editing_marker_patterns']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
