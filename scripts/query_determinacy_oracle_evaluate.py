#!/usr/bin/env python3
"""Frozen evaluation of branch and direct outputs; no model calls or file writes."""
import collections
import query_determinacy_oracle_parser as parser


def category(code,ref):
    if code=='T':return 'technical_missing'
    if code=='X':return 'invalid_or_unresolved'
    if code==ref:return 'correct'
    if code=='U':return 'overreserve'
    if ref=='U':return 'unsupported_choice'
    return 'wrong'


def evaluate(material,records,failed_ids):
    if set(material)!=set(records) or not set(failed_ids)<=set(material):raise ValueError('record IDs or failure IDs mismatch')
    grid=collections.defaultdict(dict)
    for item_id,item in material.items():
        record=records[item_id]
        if record['id']!=item_id:raise ValueError('record ID mismatch')
        code=parser.parse(record['output'],technical_complete=item_id not in failed_ids)
        key=(item['case'],item['query'])
        if item['condition'] in grid[key]:raise ValueError('duplicate condition')
        grid[key][item['condition']]={'item':item,'parsed':code}
    output=[]
    for (case,query),g in sorted(grid.items()):
        if set(g)!={'single_a','single_b','dual_sources','dual_alternatives'}:raise ValueError('missing condition')
        ref=g['dual_sources']['item']['expected']
        if ref!=g['dual_alternatives']['item']['expected']:raise ValueError('reference mismatch')
        a,b=g['single_a']['parsed'],g['single_b']['parsed']
        combined=parser.combine(a,b)
        row={'case':case,'query':query,'family':g['single_a']['item']['family'],'reference':ref,
             'single_a_id':g['single_a']['item']['id'],'single_a':a,'single_b_id':g['single_b']['item']['id'],'single_b':b,
             'combined':combined,'combined_class':category(combined,ref)}
        for method in ('dual_sources','dual_alternatives'):
            code=g[method]['parsed'];row[method+'_id']=g[method]['item']['id']
            row[method]=code;row[method+'_class']=category(code,ref)
        output.append(row)
    if len(output)!=36:raise ValueError('unexpected number of questions')
    summary={}
    for family in ('number','category'):
        for section in ('same','split'):
            rows=[r for r in output if r['family']==family and ((r['reference']=='U')==(section=='split'))]
            summary[f'{family}/{section}']={'n':len(rows)}
            for method in ('combined','dual_sources','dual_alternatives'):
                summary[f'{family}/{section}'][method]=dict(collections.Counter(r[method+'_class'] for r in rows))
    return output,summary
