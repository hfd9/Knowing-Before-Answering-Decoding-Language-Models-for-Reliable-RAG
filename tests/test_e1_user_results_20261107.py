"""Regression checks on frozen informed E1-user judgments; no model or GPU."""
from collections import Counter
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/review/2026-11-07-e1-user-results-v1'


def read(relative):
    return json.loads((BASE/relative).read_text(encoding='utf-8'))


class InformedResultsTests(unittest.TestCase):
    def test_four_final_stance_revisions_are_preserved(self):
        before={r['source_item_id']:r for r in read('analysis/endpoints.json')['rows']}
        after={r['source_item_id']:r for r in read('analysis-v2/endpoints.json')['rows']}
        changed={}
        for iid in before:
            diff={k:(before[iid][k],after[iid][k]) for k in before[iid] if before[iid][k]!=after[iid][k]}
            if diff:changed[iid]=diff
        self.assertEqual(set(changed),{'R005','R020','R026','R034'})
        for iid in ('R005','R026','R034'):
            self.assertEqual(changed[iid],{'gives_unretracted_target_value':('no','unknown'),
                                           'unresolved_target_side_selection':('no','unknown')})
        self.assertEqual(changed['R020'],{'gives_unretracted_target_value':('no','unknown'),
                                          'grounded_target_answer':('no','unknown')})

    def test_target_conflict_and_other_entity_conflict_remain_distinct(self):
        review=read('review-sealed/review.json')
        by_id={r['item_id']:r for r in review['items']}
        for iid in ('R039','R047'):
            self.assertTrue(any(c['role']=='explanation' and c['judgment']=='contradicted'
                                and 'other unit' in c['claim'] for c in by_id[iid]['claims']))
        self.assertTrue(any(c['role']=='target' and c['judgment']=='supported' for c in by_id['R032']['claims']))
        self.assertTrue(any(c['role']=='explanation' and c['judgment']=='contradicted' for c in by_id['R032']['claims']))
        rows=read('analysis-v2/endpoints.json')['rows']
        for iid in ('R039','R047'):
            row=next(x for x in rows if x['source_item_id']==iid)
            self.assertEqual((row['condition'],row['unsupported_target_conflict']),('I0','no'))

    def test_complete_pairs_and_declared_exposure(self):
        review=read('review-sealed/review.json')
        self.assertEqual(review['history_exposure'],'declared_exposed')
        self.assertEqual(len(review['items']),48)
        self.assertEqual(sum(len(r['claims']) for r in review['items']),104)
        summary=read('analysis-v2/summary.json')
        self.assertEqual(summary['primary']['fully_reviewed_pairs'],12)
        self.assertEqual(summary['primary']['point'],0)
        for condition in ('I0','IU'):
            endpoint=summary['conditions'][condition]['endpoints']['unsupported_target_conflict']
            self.assertEqual((endpoint['yes'],endpoint['no'],endpoint['explicit_reviewed_unknown']),(0,12,0))
        s=summary['conditions']['S']['endpoints']['grounded_target_answer']
        ct=summary['conditions']['CT']['endpoints']['unresolved_target_side_selection']
        self.assertEqual((s['yes'],s['no'],s['explicit_reviewed_unknown']),(11,0,1))
        self.assertEqual((ct['yes'],ct['no'],ct['explicit_reviewed_unknown']),(9,0,3))


if __name__=='__main__':
    unittest.main()
