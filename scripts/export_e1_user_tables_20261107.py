"""Export frozen informed E1-user endpoint and pair tables; no semantic scoring."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/review/2026-11-07-e1-user-results-v1'


def j(w,e):
    if 'no' in (w,e): return 'no'
    if w==e=='yes': return 'yes'
    return 'unknown'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table',choices=('items','pairs'),required=True)
    table=parser.parse_args().table
    data=json.loads((BASE/'analysis-v2/endpoints.json').read_text(encoding='utf-8'))
    rows=data['rows']
    assert len(rows)==48 and all(row['review_status']=='reviewed' for row in rows)
    if table=='items':
        fields=['scene','condition','source_item_id','technical_status','gives_unretracted_target_value',
                'provides_substantive_explanation','whole_explanation_support','overbroad_missing_information_claim',
                'grounded_target_answer','withholds_target_with_support','unsupported_target_conflict',
                'recognizes_target_conflict','unresolved_target_side_selection']
        writer=csv.DictWriter(sys.stdout,fieldnames=fields,lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({key:row[key] for key in fields})
    else:
        fields=['scene','I0_review_id','I0_W','I0_E','I0_J','IU_review_id','IU_W','IU_E','IU_J','IU_minus_I0']
        writer=csv.DictWriter(sys.stdout,fieldnames=fields,lineterminator='\n')
        writer.writeheader()
        indexed={(row['scene'],row['condition']):row for row in rows}
        for scene in range(1,13):
            values={'scene':scene}
            for condition in ('I0','IU'):
                row=indexed[(scene,condition)]
                w=row['withholds_target_with_support'];e=row['unsupported_target_conflict']
                values.update({condition+'_review_id':row['source_item_id'],condition+'_W':w,
                               condition+'_E':e,condition+'_J':j(w,e)})
            values['IU_minus_I0']=('' if 'unknown' in (values['I0_J'],values['IU_J']) else
                                   int(values['IU_J']=='yes')-int(values['I0_J']=='yes'))
            writer.writerow(values)


if __name__=='__main__':
    main()
