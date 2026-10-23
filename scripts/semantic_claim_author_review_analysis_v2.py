"""Apply the explicit author judgment addendum; preserve original sealed judgments/analysis."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='docs/review/2026-10-23-semantic-claims-author-v1'
DEST=BASE+'/analysis-v2'


def read(name):
    return json.loads((ROOT/name).read_text())


def sha(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value,ensure_ascii=False,indent=2)+'\n'


def csv_text(rows,columns):
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=columns,lineterminator='\n')
    writer.writeheader()
    writer.writerows({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(dict,list)) else r[k]
                     for k in columns} for r in rows)
    return output.getvalue()


def combine(values):
    if not values:
        return 'not_applicable'
    if set(values)&{'unsupported','contradicted'}:
        return 'no'
    return 'unknown' if 'ambiguous' in values else 'yes'


def artifacts():
    report=read(BASE+'/analysis.json');addendum=read(BASE+'/judgment-addendum.json')
    for path,expected in {**report['source_sha256'],**addendum['original_analysis_files_sha256']}.items():
        require(sha(path)==expected,'Original frozen source changed: '+path)
    by_claim={c['claim_id']:c for c in report['claims']}
    require(len(by_claim)==155 and len(report['rows'])==55,'Original size mismatch')
    for amendment in addendum['amendments']:
        claim=by_claim[amendment['claim_id']]
        require(claim['judgment']==amendment['old_judgment'],'Amendment old judgment mismatch')
        claim.update(judgment=amendment['new_judgment'],missing_link=amendment['missing_link'],
                     ambiguity=amendment['ambiguity'],judgment_addendum_source=BASE+'/judgment-addendum.json')
    for row in report['rows']:
        selected=[c for c in report['claims'] if c['item_id']==row['item_id']]
        row['all_claims_supported']=combine([c['judgment'] for c in selected])
        row['explanation_claims_supported']=combine([c['judgment'] for c in selected if c['role']!='target'])
    for group in report['groups']:
        rows=[r for r in report['rows'] if r['source_group']==group]
        report['groups'][group]['all_claims_supported']=dict(Counter(r['all_claims_supported'] for r in rows))
        report['groups'][group]['explanation_claims_supported']=dict(Counter(r['explanation_claims_supported'] for r in rows))
    report['claim_judgment_counts']=dict(Counter(c['judgment'] for c in report['claims']))
    report.update(analysis_version=2,judgment_addendum=addendum,
        source_sha256={**report['source_sha256'],**addendum['original_analysis_files_sha256'],
                       BASE+'/judgment-addendum.json':sha(BASE+'/judgment-addendum.json'),
                       'scripts/semantic_claim_author_review_analysis_v2.py':sha('scripts/semantic_claim_author_review_analysis_v2.py')})
    require(report['claim_judgment_counts']==dict(supported=101,unsupported=34,ambiguous=13,contradicted=7),
            'Final claim count mismatch')
    text=['# 55条逐主张作者复核：含明确更正的当前版本', '',
          '有历史暴露，非独立审核；155个主张实例含重复，不计算语义Accuracy或总体发生率。',
          'Q055_C03从contradicted收紧为unsupported；输入/输出原手写及v1分析全部保留。', '']
    for row in report['rows']:
        text += [f"## {row['item_id']} / {row['source_id']}",'',row['question'],'',row['answer'],'',
                 f"输入：{row['input_judgment']['answerability']}；目标答案支持：{row['target_support']}；保留未知依据：{row['withholding_matches_gap']}。",'',
                 f"全部主张有据：{row['all_claims_supported']}；解释主张有据：{row['explanation_claims_supported']}。",'']
        for claim in [c for c in report['claims'] if c['item_id']==row['item_id']]:
            text += [f"### {claim['claim_id']} / {claim['role']} / {claim['judgment']}",'',
                     '主张：'+claim['claim'],'','原文：'+claim['output_reference']['quote'],'',
                     '缺失/所需：'+claim['missing_link'],'','歧义/边界：'+claim['ambiguity'],'']
            text += [f"- D{v['document_index']} [{v['start']},{v['end']})：{v['quote']}" for v in claim['document_support']]
            text += ['']
    rows=report['rows'];claims=report['claims']
    return {DEST+'/report.json':encoded(report),DEST+'/claims.md':'\n'.join(text),
        DEST+'/rows.csv':csv_text(rows,['item_id','source_id','source_group','original_id','original_condition',
            'gives_specific_target_answer','target_support','withholding_matches_gap','all_claims_supported',
            'explanation_claims_supported','claim_count','prior_behavior_fields','prior_author_rationale']),
        DEST+'/claims.csv':csv_text(claims,['item_id','claim_id','source_id','source_sentence_unit','claim',
            'judgment','role','output_reference','document_support','missing_link','ambiguity'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['analyze','verify'],required=True)
    args=parser.parse_args()
    files=artifacts()
    for path,content in files.items():
        target=ROOT/path;data=content.encode()
        if args.stage=='analyze':
            require(not target.exists() or target.read_bytes()==data,'Refuse changed v2 output: '+path)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        else:
            require(target.read_bytes()==data,'V2 replay mismatch: '+path)
    report=json.loads(files[DEST+'/report.json'])
    print(encoded(dict(stage=args.stage,items=55,claims=155,claim_counts=report['claim_judgment_counts'],
                       independent_reviews=0,amendments=1,original_files_overwritten=False)))


if __name__=='__main__':
    main()
