"""Connect sealed handwritten input/claim reviews; CPU only, history-exposed author review."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'docs/review/2026-10-23-semantic-claims-v1'
DEST = 'docs/review/2026-10-23-semantic-claims-author-v1'
SPEC = 'prompts/semantic_claim_author_review_v1.json'
FIELDS = ['sentence_unit','verbatim_anchor','proposition','judgment','document_indices',
          'missing_link','ambiguity','role']


def read(path):
    return json.loads((ROOT/path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def encoded(data):
    return json.dumps(data, ensure_ascii=False, indent=2)+'\n'


def csv_text(rows, columns):
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(list,dict))
                      else r[k] for k in columns} for r in rows)
    return out.getvalue()


def span(text, start, end, **extra):
    require(0 <= start < end <= len(text), 'Invalid text span')
    return dict(start=start,end=end,quote=text[start:end],
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),**extra)


def aggregate(claims):
    if not claims:
        return 'not_applicable'
    values={c['judgment'] for c in claims}
    if values & {'contradicted','unsupported'}:
        return 'no'
    return 'unknown' if 'ambiguous' in values else 'yes'


def compute():
    spec=read(SPEC)
    require(spec['identity']['independent'] is False and spec['limits']['remaining_original_fit_budget']==0,
            'Review identity or budget mismatch')
    manifest=read(PACKAGE+'/manifest.json')
    preserved={**manifest['source_sha256'],**manifest['payload_sha256'],
               PACKAGE+'/manifest.json':sha(PACKAGE+'/manifest.json')}
    for path,expected in preserved.items():
        require(sha(path)==expected,'Original source/package changed: '+path)
    input_seal=read(DEST+'/input-seal.json')
    output_seal=read(DEST+'/output-seal.json')
    require(input_seal['manual_sha256']==sha(DEST+'/input-manual.json') and
            input_seal['input_packet_sha256']==sha(PACKAGE+'/public/input_packet.json') and
            input_seal['spec_sha256']==sha(SPEC), 'Input seal mismatch')
    require(output_seal['input_seal_sha256']==sha(DEST+'/input-seal.json') and
            input_seal['sealed_at']<output_seal['sealed_at'], 'Seal order mismatch')
    for path,expected in output_seal['manual_files_sha256'].items():
        require(sha(path)==expected,'Output manual changed after seal')
    require(input_seal['prior_output_exposure'] is True and input_seal['independent'] is False
            and output_seal['independent'] is False, 'Exposure missing')
    inputs=read(PACKAGE+'/public/input_packet.json')['items']
    outputs={r['item_id']:r for r in read(PACKAGE+'/public/output_packet.json')['items']}
    source_cases={r['item_id']:r for r in read(PACKAGE+'/coordinator/cases.json')['cases']}
    manual_input=read(DEST+'/input-manual.json')
    inrows={r[0]:dict(zip(manual_input['field_order'],r)) for r in manual_input['rows']}
    manual_output={}
    for path in sorted(output_seal['manual_files_sha256']):
        data=read(path)['items']
        require(not set(data)&set(manual_output),'Duplicate output review')
        manual_output.update(data)
    require(len(inputs)==len(outputs)==len(inrows)==len(manual_output)==55
            and set(inrows)==set(outputs)==set(manual_output)==set(source_cases), 'Incomplete55')
    rows,claims,inventory=[],[],[]
    for inp in inputs:
        iid=inp['item_id'];ir=inrows[iid];manual=manual_output[iid];out=outputs[iid];case=source_cases[iid]
        require(ir['answerability'] in spec['input_values'], 'Unknown input judgment')
        require(len(inp['documents'])==5 and len(manual['target'])==3, 'Malformed input or target fields')
        indices=ir['document_indices']
        input_references=[span(inp['documents'][j-1],0,len(inp['documents'][j-1]),document_index=j)
                          for j in indices]
        for j,doc in enumerate(inp['documents'],1):
            inventory.append(dict(item_id=iid,document_index=j,sha256=hashlib.sha256(doc.encode()).hexdigest()))
        item_claims=[];covered=set()
        for number,raw in enumerate(manual['claims'],1):
            require(len(raw)==len(FIELDS),'Malformed manual claim')
            c=dict(zip(FIELDS,raw));u=c['sentence_unit']
            require(type(u) is int and 1<=u<=len(out['candidate_sentence_units']),'Invalid sentence reference')
            unit=out['candidate_sentence_units'][u-1];anchor=c['verbatim_anchor']
            require(unit['quote'].count(anchor)==1,'Missing/ambiguous output anchor: '+iid+' '+anchor)
            start=unit['start']+unit['quote'].index(anchor)
            require(c['judgment'] in spec['claim_values'] and c['proposition'] and c['missing_link']
                    and c['ambiguity'] and c['document_indices'], 'Empty/invalid authored judgment')
            references=[]
            for j in c['document_indices']:
                require(type(j) is int and 1<=j<=5,'Invalid document index')
                doc=inp['documents'][j-1]
                references.append(span(doc,0,len(doc),document_index=j))
            claim=dict(item_id=iid,claim_id=f'{iid}_C{number:02d}',source_id=case['source_id'],
                source_sentence_unit=unit['unit_id'],claim=c['proposition'],judgment=c['judgment'],role=c['role'],
                output_reference=span(out['answer'],start,start+len(anchor)),
                document_support=references,missing_link=c['missing_link'],ambiguity=c['ambiguity'],
                all_five_documents_checked=True,history_exposed=True,independent=False)
            item_claims.append(claim);covered.add(u)
        require(covered==set(range(1,len(out['candidate_sentence_units'])+1)), 'Uncovered sentence unit: '+iid)
        given,target_support,withholding=manual['target']
        require(type(given) is bool and target_support in spec['claim_values']
                and withholding in spec['claim_values'], 'Invalid target endpoint')
        require((not given)==(target_support=='not_applicable') and
                given==(withholding=='not_applicable'), 'Target endpoint applicability mismatch')
        explanation=[c for c in item_claims if c['role']!='target']
        rows.append(dict(item_id=iid,source_id=case['source_id'],source_group=case['selection_group'],
            original_id=case['original_id'],original_condition=case['original_condition'],
            question=inp['question'],answer=out['answer'],input_judgment=ir,
            input_citations=input_references,gives_specific_target_answer=given,target_support=target_support,
            withholding_matches_gap=withholding,all_claims_supported=aggregate(item_claims),
            explanation_claims_supported=aggregate(explanation),
            claim_count=len(item_claims),covered_sentence_units=len(covered),
            prior_behavior_fields=case['prior_behavior_fields'],
            prior_author_rationale=case['prior_behavior_rationale'],
            old_new_endpoint_comparison_not_adjudication=True,
            full_assertion_coverage='handwritten declaration; text unit coverage is checked, atomic completeness is not machine certified'))
        claims.extend(item_claims)
    require(len(claims)==output_seal['claim_instances']==155,'Manual claim count mismatch')
    groups={}
    for group in sorted({r['source_group'] for r in rows}):
        selected=[r for r in rows if r['source_group']==group]
        groups[group]=dict(items=len(selected),target_given=sum(r['gives_specific_target_answer'] for r in selected),
            target_support=dict(Counter(r['target_support'] for r in selected)),
            all_claims_supported=dict(Counter(r['all_claims_supported'] for r in selected)),
            explanation_claims_supported=dict(Counter(r['explanation_claims_supported'] for r in selected)))
    report=dict(status='history_exposed_author_claim_review_complete',independent_semantic_approvals=0,
        formal_gate=False,formal_labels_added=0,original_ratings_overwritten=False,
        independent_templates_overwritten=False,items=55,document_slots=275,
        unique_document_texts=len({r['sha256'] for r in inventory}),sentence_units=82,claim_instances=len(claims),
        input_judgment_counts=dict(Counter(r['input_judgment']['answerability'] for r in rows)),
        claim_judgment_counts=dict(Counter(c['judgment'] for c in claims)),
        target_support_counts=dict(Counter(r['target_support'] for r in rows)),groups=groups,
        new_model_calls=0,new_fits=0,remaining_original_design_fits=0,held_out_380_accessed=False,
        input_sealed_at=input_seal['sealed_at'],output_sealed_at=output_seal['sealed_at'],
        interpretation='Purpose-selected55, history-exposed author claims only. Claim instances include repetitions and depend on decomposition; no population rate, independent semantic accuracy, mechanism or causal-use conclusion. The9 ambiguous inputs do not rewrite original60 denominator. No GPU task is made ready by this review.',
        source_sha256={**preserved,**{p:sha(p) for p in [SPEC,DEST+'/input-manual.json',
                         DEST+'/input-seal.json',DEST+'/output-seal.json',
                         'scripts/semantic_claim_author_review.py']+sorted(output_seal['manual_files_sha256'])}},
        rows=rows,claims=claims)
    return report,inventory


def artifacts():
    report,inventory=compute()
    rows,claims=report['rows'],report['claims']
    text=['# 55条有历史暴露的逐主张作者复核', '',
          '实际独立语义批准仍0。原评分、独立空白模板和正式门禁不改写。',
          '155是本轮手写主张实例，包含重复；82逐句单元覆盖不自动认证原子拆分完整。', '']
    for row in rows:
        text += [f"## {row['item_id']} / {row['source_id']}", '',row['question'],'',row['answer'],'',
                 f"输入判断：{row['input_judgment']['answerability']}；目标答案：{row['target_support']}；保留未知依据：{row['withholding_matches_gap']}。",'',
                 f"完整主张均有据：{row['all_claims_supported']}；解释主张均有据：{row['explanation_claims_supported']}。",'']
        for c in [c for c in claims if c['item_id']==row['item_id']]:
            text += [f"### {c['claim_id']} / {c['role']} / {c['judgment']}",'',
                     '主张：'+c['claim'],'','输出原文：'+c['output_reference']['quote'],'',
                     '缺失/所需环节：'+c['missing_link'],'','歧义/边界：'+c['ambiguity'],'',
                     '文档证据/背景（不自动表示对该主张的正面支持）：','']
            text += [f"- D{v['document_index']} [{v['start']},{v['end']})：{v['quote']}" for v in c['document_support']]
            text += ['']
    columns=['item_id','source_id','source_group','original_id','original_condition',
             'gives_specific_target_answer','target_support','withholding_matches_gap',
             'all_claims_supported','explanation_claims_supported','claim_count',
             'prior_behavior_fields','prior_author_rationale']
    return {DEST+'/analysis.json':encoded(report),DEST+'/rows.csv':csv_text(rows,columns),
        DEST+'/claims.csv':csv_text(claims,['item_id','claim_id','source_id','source_sentence_unit','claim',
            'judgment','role','output_reference','document_support','missing_link','ambiguity']),
        DEST+'/claims.md':'\n'.join(text),DEST+'/reading-inventory.json':encoded(dict(
            documents=inventory,slots=275,unique_texts=140,
            declaration='本轮去重后全文阅读全部140文本，所有275槽逐项连接；非独立语义认证。'))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['analyze','verify'],required=True)
    args=parser.parse_args()
    files=artifacts()
    for path,content in files.items():
        target=ROOT/path;data=content.encode()
        if args.stage=='analyze':
            require(not target.exists() or target.read_bytes()==data,'Refuse changed analysis output: '+path)
            target.write_bytes(data)
        else:
            require(target.read_bytes()==data,'Analysis replay mismatch: '+path)
    report=json.loads(files[DEST+'/analysis.json'])
    print(encoded({k:report[k] for k in ['items','claim_instances','input_judgment_counts',
        'claim_judgment_counts','target_support_counts','groups','independent_semantic_approvals']}))


if __name__=='__main__':
    main()
