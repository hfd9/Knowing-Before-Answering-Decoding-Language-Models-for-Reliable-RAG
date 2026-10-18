"""Validate explicit assistant ratings/attributions; never infer semantic labels."""

import argparse
from collections import Counter
import csv
import html
import io
import json
from pathlib import Path
import random

import validation_semantic_pilot as pilot


def summarize(base):
    read,digest=pilot.read,pilot.digest
    protocol=read(base/'protocol.json')
    assert digest(pilot.ROOT/'scripts/validation_semantic_pilot.py')==protocol['script_sha256']
    for path,expected in read(base/'coordinator/protected_hashes.json').items():
        assert digest(pilot.ROOT/path)==expected,f'Protected source changed: {path}'
    values=pilot.validate_inputs(base,base/'input_ratings.json')
    assert read(base/'input_review_seal.json')['input_ratings_sha256']==digest(base/'input_ratings.json')
    revealed=read(base/'revealed/model_outputs.json')
    assert revealed['input_ratings_sha256']==digest(base/'input_ratings.json')
    packet=read(base/'public/inputs.json')
    inputs={r['review_id']:r for r in packet['records']}
    ratings={r['review_id']:r for r in values}
    outputs={r['review_id']:r for r in revealed['records']}
    attrs=read(base/'model_attributions.json')
    assert len(attrs)==30 and {r['review_id'] for r in attrs}==set(inputs)
    source=[json.loads(line) for line in (pilot.ROOT/protocol['source_path']).read_text().splitlines()]
    ordered=list(dict.fromkeys(r['original_id'] for r in source))
    assert random.Random(42).sample(ordered,10)==protocol['selected_original_ids']
    source={r['id']:r for r in source}
    mapping=read(base/'coordinator/mapping.json')
    for key,row in inputs.items():
        original=source[mapping[key]]
        assert row['question']==original['question']
        assert [packet['documents'][ref] for ref in row['doc_refs']]==original['docs']
        assert outputs[key]['id']==original['id'] and outputs[key]['published_mode']==original['true_mode']
    known=[key for key in ratings if ratings[key]['semantic_mode']!='unknown']
    comparison=[]
    for a in attrs:
        key=a['review_id'];out=outputs[key];rating=ratings[key];model=out['v4']
        raw=json.loads(model['raw_output'])
        expected=('not_scored_input_unknown' if rating['semantic_mode']=='unknown' else
                  'technical_invalid' if model['draft']['status']!='valid_structure' else
                  'agreement' if model['draft']['semantic_mode']==rating['semantic_mode'] else 'mismatch')
        assert a['classification_judgment']==expected,(key,expected)
        assert a['rationale_reviewed_in_full'] is True and a['v4_citations_checked_against_original'] is True
        assert a['explanation'].strip() and len(a['issue_tags'])==len(set(a['issue_tags']))
        if raw['citation_ids']:
            assert a['citation_support'] in ['supported','partial','unsupported','unknown']
        else:
            assert a['citation_support']=='not_applicable'
        entry=dict(review_id=key,id=out['id'],question=inputs[key]['question'],published_mode=out['published_mode'],
                   input_semantic_mode=rating['semantic_mode'],input_confidence=rating['confidence'],
                   v4_report_mode=model['draft']['semantic_mode'],v4_raw_mode=raw['semantic_mode'],
                   v4_status=model['draft']['status'],classification_judgment=expected,
                   primary_issue=a['primary_issue'],issue_tags=';'.join(a['issue_tags']),
                   citation_support=a['citation_support'],explanation=a['explanation'])
        entry.update({name:values[key]['pred_mode'] or 'invalid'
                      for name,values in {n:{r['review_id']:r['previous'][n] for r in revealed['records']}
                                         for n in ['legacy_chat8','definitions','decision_order','illustrations']}.items()})
        comparison.append(entry)
    comparison.sort(key=lambda r:r['review_id'])
    methods={}
    for name in ['legacy_chat8','definitions','decision_order','illustrations','v4_report_mode']:
        modes={r['review_id']:r[name] for r in comparison}
        agrees=[key for key in known if modes[key]==ratings[key]['semantic_mode']]
        methods[name]=dict(input_known_denominator=len(known),agreement_count=len(agrees),agreement_fraction=len(agrees)/len(known),
                           unknown_input_excluded=len(ratings)-len(known),agreement_ids=agrees,
                           mode_counts_all30=dict(Counter(modes.values())))
    matrix={mode:dict.fromkeys(['answer','refuse','conflict','unknown'],0) for mode in ['answer','refuse','conflict']}
    for key in known:
        matrix[ratings[key]['semantic_mode']][outputs[key]['v4']['draft']['semantic_mode']]+=1
    changed=[r for r in comparison if r['input_semantic_mode']!='unknown' and r['input_semantic_mode']!=r['published_mode']]
    citations=[]
    for key,rating in ratings.items():
        for i,cite in enumerate(rating['citations'],1):
            doc=packet['documents'][inputs[key]['doc_refs'][cite['doc_id']-1]]
            starts=[];cursor=0
            while True:
                start=doc.find(cite['quote'],cursor)
                if start<0:break
                starts.append(dict(start=start,end=start+len(cite['quote'])));cursor=start+1
            assert starts
            citations.append(dict(review_id=key,citation_index=i,**cite,occurrences=starts))
    summary=dict(status='review_complete_diagnostic_assistant_not_independent_gold',instances=30,base_questions=10,
                 input_review_seal=read(base/'input_review_seal.json'),selected_original_ids=protocol['selected_original_ids'],
                 provenance=read(base/'exposure_disclosure.json'),unique_documents=len(packet['documents']),
                 unique_document_characters=sum(map(len,packet['documents'].values())),
                 input_mode_counts=dict(Counter(r['semantic_mode'] for r in values)),
                 input_confidence_counts=dict(Counter(r['confidence'] for r in values)),
                 published_mode_counts=dict(Counter(r['published_mode'] for r in outputs.values())),
                 known_input_publication_disagreements=[dict(review_id=r['review_id'],id=r['id'],published_mode=r['published_mode'],input_mode=r['input_semantic_mode']) for r in changed],
                 unknown_input_ids=[key for key in ratings if ratings[key]['semantic_mode']=='unknown'],
                 v4_classification_judgments=dict(Counter(r['classification_judgment'] for r in attrs)),
                 v4_matrix_on_known_inputs=matrix,method_mode_agreement=methods,
                 primary_issue_counts=dict(Counter(r['primary_issue'] for r in attrs)),
                 issue_tag_counts_nonexclusive=dict(Counter(tag for r in attrs for tag in r['issue_tags'])),
                 citation_support_all_raw_decisions=dict(Counter(r['citation_support'] for r in attrs)),
                 citation_support_valid_structures=dict(Counter(r['citation_support'] for r in attrs if outputs[r['review_id']]['v4']['draft']['status']=='valid_structure')),
                 input_citations_checked=len(citations),
                 input_ratings_sha256=digest(base/'input_ratings.json'),model_attributions_sha256=digest(base/'model_attributions.json'),
                 protocol_sha256=digest(base/'protocol.json'),
                 limitation='Single context-exposed assistant; 10 base-question pilot, no population accuracy or causal mechanism claim. Input unknowns unscored. Descriptive issue tags can overlap. No labels imported or GPU run.')
    return summary,comparison,citations


def write_outputs(base,summary,comparison,citations):
    pilot.save_new(base/'reports/summary.json',summary)
    pilot.save_new(base/'reports/input_citation_offsets.json',citations)
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=list(comparison[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(comparison)
    target=base/'reports/comparison.csv';target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.read_text()!=out.getvalue():raise ValueError('Existing comparison changed')
    target.write_text(out.getvalue())
    lines=['# 30条验证集助手语义诊断', '',summary['limitation'], '',
           '输入判断：'+str(summary['input_mode_counts']),
           'v4类别判断：'+str(summary['v4_classification_judgments']),
           '主要问题：'+str(summary['primary_issue_counts']), '',
           '| 审核编号 | 源编号 | 发布类别 | 封存语义 | v4正式/原始 | 归因 | 引文支持 |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for r in comparison:
        lines.append(f'| {r["review_id"]} | {r["id"]} | {r["published_mode"]} | {r["input_semantic_mode"]} | {r["v4_report_mode"]}/{r["v4_raw_mode"]} | {r["primary_issue"]} | {r["citation_support"]} |')
    lines+=['','## 逐条归因','']
    for r in comparison:lines += [f'### {r["review_id"]} / {r["id"]}', '',r['question'],'',r['explanation'],'']
    text='\n'.join(lines)+'\n';target=base/'reports/summary.md'
    if target.exists() and target.read_text()!=text:raise ValueError('Existing summary changed')
    target.write_text(text)
    packet=pilot.read(base/'public/inputs.json')
    page=['<!doctype html><meta charset="utf-8"><title>30-input semantic review</title>',
          '<style>body{max-width:1000px;margin:30px auto;font:16px sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #aaa}</style>',
          '<h1>Input-only material</h1><p>Only questions and complete original documents; no source labels or model outputs. Repeated packet use is not evidence of an independent reviewer.</p>']
    for r in packet['records']:
        page += [f'<article><h2>{r["review_id"]}</h2><p>{html.escape(r["question"])}</p>']
        for i,ref in enumerate(r['doc_refs'],1):
            page.append(f'<details><summary>Document {i}</summary><pre>{html.escape(packet["documents"][ref])}</pre></details>')
        page.append('</article>')
    target=base/'public/input_review.html';text='\n'.join(page)
    if target.exists() and target.read_text()!=text:raise ValueError('Existing page changed')
    target.write_text(text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir',type=Path,default=pilot.DEFAULT)
    parser.add_argument('--check_only',action='store_true')
    args=parser.parse_args()
    summary,comparison,citations=summarize(args.run_dir.resolve())
    if not args.check_only:write_outputs(args.run_dir.resolve(),summary,comparison,citations)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
