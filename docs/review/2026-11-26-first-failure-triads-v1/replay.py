"""Cross-check triad grouping against the frozen 24-output informed ratings."""
import collections
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / 'docs/review/2026-11-26-two-rule-7b-first-results-v1/ratings.csv'


def run():
    prior = list(csv.DictReader(OLD.open()))
    source = {(row['case'], row['route']): row for row in prior}
    assert len(prior) == len(source) == 24
    groups = list(csv.DictReader((HERE / 'triads.csv').open()))
    assert len(groups) == len({(g['rule'], g['scenario'], g['route']) for g in groups}) == 8
    counts = collections.Counter()
    for g in groups:
        rule, scenario, route = (g[k] for k in ('rule', 'scenario', 'route'))
        rows = {state: source[(f'{rule}/{scenario}/{state}', route)]
                for state in ('missing', 'old', 'new')}
        for state in ('missing', 'old', 'new'):
            assert g[state + '_content'] == rows[state]['content_status']
        both = rows['old']['content_status'] == rows['new']['content_status'] == 'correct'
        assert g['both_date_content_correct'] == ('yes' if both else 'no')
        missing_failed = rows['missing']['content_status'] != 'correct'
        if both:
            counts['both_date_content_correct'] += 1
            if missing_failed:
                counts['both_date_content_correct_missing_not_correct'] += 1
        if g['known_whole_reply_and_date_citation'] == 'yes':
            assert both
            for state, expected in (('old', 'E1'), ('new', 'E2')):
                assert expected in rows[state]['citation_ids'].split('|')
            counts['known_whole_reply_and_date_citation'] += 1
            if missing_failed:
                counts['known_whole_reply_and_date_citation_missing_not_correct'] += 1
    return counts


if __name__ == '__main__':
    print(dict(run()))
