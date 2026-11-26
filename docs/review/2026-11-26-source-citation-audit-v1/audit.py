"""Replay ID occurrence and informed content labels; no model or semantic scoring."""
import collections
import csv
import json
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
RESULT = ROOT / 'docs/review/2026-11-26-two-rule-7b-first-results-v1'


def run():
    ratings = list(csv.DictReader((RESULT / 'ratings.csv').open()))
    rules = json.loads((ROOT / 'docs/review/2026-11-26-new-rule-materials-v1/rules.json').read_text())['rules']
    assert len(ratings) == 24
    with ZipFile(RESULT / 'raw.zip') as z:
        plan = json.loads(z.read('prepared/plan.json'))
        outputs = {task['id']: json.loads(z.read(f'run/{i:02d}.record.json'))['output']
                   for i, task in enumerate(plan)}
    groups = collections.Counter()
    for row in ratings:
        key = row['case'] + '/' + row['route']
        ids = set(re.findall(r'\b(?:E\d+|F\d+)\b', outputs[key]))
        assert ids == set(row['citation_ids'].split('|'))
        state = row['case'].split('/')[-1]
        groups[('all', 'f1_mentioned' if 'F1' in ids else 'f1_not_mentioned')] += 1
        if state == 'missing':
            scope = (row['route'], 'missing')
            groups[scope + ('total',)] += 1
            if {'E1', 'E2'} <= ids:
                groups[scope + ('both_ids_present',)] += 1
                if row['content_status'] == 'correct':
                    groups[scope + ('both_ids_and_correct_content',)] += 1
        else:
            scope = (row['route'], 'known')
            groups[scope + ('total',)] += 1
            expected = 'E1' if state == 'old' else 'E2'
            if expected in ids:
                groups[scope + ('expected_id_present',)] += 1
    sec = next(r for r in rules if r['id'] == 'adviser_aum')
    irs = next(r for r in rules if r['id'] == 'eitc_investment')
    assert all('qualified client' not in e['excerpt'].lower() for e in sec['evidence'])
    assert all('taxable years beginning' not in e['excerpt'].lower() for e in irs['evidence'])
    return {'observations': {'/'.join(k): v for k, v in sorted(groups.items())},
            'sec_snippets_omit_qualified_client_subject': True,
            'irs_snippets_omit_source_year_phrase': True,
            'semantic_support_automatically_evaluated': False}


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
