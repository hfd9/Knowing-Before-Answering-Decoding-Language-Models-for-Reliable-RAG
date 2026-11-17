#!/usr/bin/env python3
"""Replay model-extracted candidates with exact cached branch prompts, without oracle gating."""
import collections
import json
import re

import query_determinacy_oracle_evaluate as qa_evaluator
import query_determinacy_oracle_parser as qa_parser
import query_determinacy_oracle_results as qa_results
import query_determinacy_template_world_extraction as template
import query_determinacy_world_extract_parser as world_parser
import query_determinacy_world_extract_results as world_results


def prompts_from_candidates(direct_prompt,values):
    """Use subject/format only; never compare predicted values to gold candidates."""
    lines=direct_prompt.splitlines()
    if len(lines)!=4 or lines[0]!=template.PREFIX or not lines[2].startswith('问题：') or lines[3]!=template.SUFFIX:
        raise ValueError('unrecognized outer template')
    evidence=lines[1];axiom=template.AXIOM if evidence.startswith(template.AXIOM) else ''
    rest=evidence[len(axiom):]
    match=template.SOURCE.match(rest)
    if match:tail=template.SOURCE_TAIL
    else:match=template.ALT.match(rest);tail=template.ALT_TAIL
    if not match or rest[match.end():]!=tail:raise ValueError('unrecognized source template')
    subject=match['subject']
    if not re.fullmatch(r'虚构样本[HK]\d{2}的记录(?:数值|代码)',subject):raise ValueError('bad subject')
    if type(values) is not list or len(values)!=2 or any(type(v) is not str for v in values):raise ValueError('bad extracted values')
    numeric=subject.endswith('数值')
    if numeric:
        if axiom or any(not re.fullmatch(r'[0-9]+',v) for v in values):raise ValueError('bad numeric syntax')
        rendered=[v+'个单位' for v in values]
    else:
        if not axiom or any(not re.fullmatch(r'[A-Z][0-9]',v) for v in values):raise ValueError('bad code syntax')
        rendered=['“'+v+'”' for v in values]
    if rendered[0]==rendered[1]:raise ValueError('identical extracted values')
    return [f'{template.PREFIX}\n{axiom}假设{subject}确定为{v}。\n{lines[2]}\n{template.SUFFIX}' for v in rendered]


def replay():
    qa_results.analyze();world_results.analyze()
    qa_data=qa_results.run.inputs();world_data=world_results.run.inputs()
    qa_archive=json.loads((qa_results.RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    world_archive=json.loads((world_results.RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    qa_records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in qa_archive if '/records/' in x['path'])}
    world_records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in world_archive if '/records/' in x['path'])}
    qa_prompts={x['prompt']:x for x in qa_data.values()}
    if len(qa_prompts)!=144:raise ValueError('ambiguous cache prompts')
    worlds={(x['case'],x['condition']):x for x in world_data.values()}
    if len(worlds)!=24:raise ValueError('world extraction case mapping mismatch')
    rows=[]
    for item in qa_data.values():
        if item['condition'] not in ('dual_sources','dual_alternatives'):continue
        world_item=worlds[(item['case'],item['condition'])]
        status,values=world_parser.parse(world_records[world_item['id']]['output'])
        branch_ids=[];branch_codes=[]
        if status!='parsed':
            outcome='X';reason='extraction_invalid'
        else:
            try:prompts=prompts_from_candidates(item['prompt'],values)
            except ValueError:outcome='X';reason='candidate_syntax_invalid'
            else:
                if any(p not in qa_prompts for p in prompts):outcome='X';reason='branch_cache_miss'
                else:
                    matches=[qa_prompts[p] for p in prompts]
                    branch_ids=[x['id'] for x in matches]
                    branch_codes=[qa_parser.parse(qa_records[x]['output']) for x in branch_ids]
                    outcome=qa_parser.combine(*branch_codes);reason='cached_branches'
        reference=item['expected']  # Reference used only here, after the pipeline outcome is fixed.
        direct=qa_parser.parse(qa_records[item['id']]['output'])
        rows.append({'id':item['id'],'case':item['case'],'query':item['query'],'family':item['family'],
                     'condition':item['condition'],'world_extraction_id':world_item['id'],'world_parse':status,
                     'predicted_values':values,'branch_ids':branch_ids,'branch_codes':branch_codes,'reason':reason,
                     'combined':outcome,'combined_class':qa_evaluator.category(outcome,reference),
                     'direct':direct,'direct_class':qa_evaluator.category(direct,reference),'reference':reference})
    if len(rows)!=72:raise ValueError('unexpected direct item count')
    summary={}
    for cond in ('dual_sources','dual_alternatives'):
        group=[r for r in rows if r['condition']==cond]
        summary[cond]={'n':len(group),'combined':dict(collections.Counter(r['combined_class'] for r in group)),
                       'direct':dict(collections.Counter(r['direct_class'] for r in group)),
                       'pipeline_reason':dict(collections.Counter(r['reason'] for r in group))}
    return rows,summary


if __name__=='__main__':
    _,summary=replay();print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
