#!/usr/bin/env python3
"""Replay exact-template extraction and cached single-world outputs; no model calls."""
import collections
import json

import query_determinacy_oracle_results as results
import query_determinacy_oracle_parser as parser
import query_determinacy_oracle_evaluate as evaluator
import query_determinacy_template_world_extraction as extraction


def replay():
    results.analyze()  # verifies frozen results and live/archived source bytes
    data=results.run.inputs()
    archive=json.loads((results.RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in archive if '/records/' in x['path'])}
    by_prompt={item['prompt']:item for item in data.values()}
    if len(by_prompt)!=144:raise ValueError('duplicate inputs prevent unambiguous cache lookup')
    rows=[]
    for item in data.values():
        if item['condition'] not in ('dual_sources','dual_alternatives'):continue
        branches=extraction.branch_prompts(item['prompt'])
        try:matched=[by_prompt[x] for x in branches]
        except KeyError as error:raise ValueError('extracted branch is not an exact cached prompt') from error
        if any(x['case']!=item['case'] or x['query']!=item['query'] for x in matched):
            raise ValueError('matched a different problem')
        if {x['condition'] for x in matched}!={'single_a','single_b'}:raise ValueError('branch match is not the two single worlds')
        values=[parser.parse(records[x['id']]['output']) for x in matched]
        code=parser.combine(*values)
        direct=parser.parse(records[item['id']]['output'])
        ref=item['expected']
        rows.append({'id':item['id'],'case':item['case'],'query':item['query'],'family':item['family'],
                     'condition':item['condition'],'reference':ref,'branch_1_id':matched[0]['id'],
                     'branch_1':values[0],'branch_2_id':matched[1]['id'],'branch_2':values[1],
                     'combined':code,'combined_class':evaluator.category(code,ref),
                     'direct':direct,'direct_class':evaluator.category(direct,ref)})
    if len(rows)!=72:raise ValueError('direct prompt count')
    summary={}
    for condition in ('dual_sources','dual_alternatives'):
        group=[r for r in rows if r['condition']==condition]
        summary[condition]={'n':len(group),'combined':dict(collections.Counter(r['combined_class'] for r in group)),
                            'direct':dict(collections.Counter(r['direct_class'] for r in group))}
    return rows,summary


if __name__=='__main__':
    _,summary=replay();print(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2))
