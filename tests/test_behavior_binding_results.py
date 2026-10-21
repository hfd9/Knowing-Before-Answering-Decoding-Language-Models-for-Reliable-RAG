"""CPU checks for human-rating evidence, complete pairing and unknown denominators."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import behavior_binding_results as review


class ReviewTests(unittest.TestCase):
    def test_unknown_retains_full_denominator_and_no_point(self):
        rate=review.rate([{'value':'yes'},{'value':'no'},{'value':'unknown'}],'value')
        self.assertEqual((rate['eligible'],rate['identification_lower'],rate['identification_upper']),
                         (3,1/3,2/3))
        self.assertIsNone(rate['point'])

    def test_quote_offset_text_and_hash_tampering_rejected(self):
        text='A target code is supplied.'
        citation=dict(start=0,end=len(text),quote=text,text_sha256=review.hashlib.sha256(text.encode()).hexdigest())
        review.check_quote(citation,text)
        for change in [dict(start=-1),dict(end=len(text)+1),dict(quote='other'),dict(text_sha256='wrong')]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                review.check_quote(dict(citation,**change),text)

    def test_full_real_packet_is_valid_but_duplicate_or_unreviewed_is_not(self):
        packet=review.read(review.RUN+'/behavior_review/packet.json')
        ratings=review.read(review.PREFIX+'-ratings.json')
        self.assertEqual(len(review.validate_ratings(packet,ratings)),48)
        for kind in ['duplicate','unreviewed','invalid','missing_quote']:
            bad=copy.deepcopy(ratings)
            if kind=='duplicate':bad['ratings'][0]=bad['ratings'][1]
            elif kind=='unreviewed':bad['ratings'][0]['status']='unreviewed'
            elif kind=='invalid':bad['ratings'][0][review.FIELDS[0]]='maybe'
            else:bad['ratings'][0]['output_citations']=[]
            with self.subTest(kind=kind),self.assertRaises(ValueError):review.validate_ratings(packet,bad)

    def fixture_rows(self):
        return [dict(id=f'{i}_{c}_{v}',original_id=str(i),question='Target question '+str(i),
            target_entity='T'+str(i),condition=c,variant=v,item_id=f'R{i}{c}{v}',raw_output='Synthetic',
            **{f:('yes' if f=='supported_target_answer' and c=='S' else 'no') for f in review.FIELDS})
            for i in range(12) for c in ['S','I'] for v in ['v1','v2']]

    def test_pairs_keep_all_four_cells_and_all12_bases(self):
        rows=self.fixture_rows();pairs=review.make_pairs(rows)
        self.assertEqual(len(pairs),12)
        self.assertEqual(review.rate(pairs,'S_both_supported')['yes'],12)
        self.assertEqual(review.rate(pairs,'I_both_follow_cell_distractor')['yes'],0)
        for bad in [rows[:-1],rows[:-1]+[rows[0]]]:
            with self.assertRaises(ValueError):review.make_pairs(bad)
        rows[0]['question']='Wrong base question'
        with self.assertRaisesRegex(ValueError,'Mixed base'):review.make_pairs(rows)

    def test_paired_unknown_is_not_filled_no(self):
        rows=self.fixture_rows()
        for r in rows:
            if r['original_id']=='0' and r['condition']=='I':r['adopts_cell_distractor_value']='unknown'
        result=review.rate(review.make_pairs(rows),'I_both_follow_cell_distractor')
        self.assertEqual(result['unknown'],1)
        self.assertIsNone(result['point'])

    def test_ack_and_answer_do_not_establish_output_order(self):
        self.assertEqual(review.acknowledgment_then_answer(dict(has_substantive_target_answer='yes',
                         acknowledges_insufficiency='yes')),'unknown')
        self.assertEqual(review.acknowledgment_then_answer(dict(has_substantive_target_answer='no',
                         acknowledges_insufficiency='yes')),'no')


if __name__=='__main__':unittest.main()
