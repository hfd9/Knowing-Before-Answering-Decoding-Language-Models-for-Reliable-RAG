#!/usr/bin/env python3
"""Frozen evaluation of candidate extraction outputs, without model calls."""
import collections
import query_determinacy_world_extract_parser as parser


def evaluate(material,records,failed_ids):
    if set(material)!=set(records) or not set(failed_ids)<=set(material):raise ValueError('record IDs or failure IDs differ')
    output=[]
    for key,item in sorted(material.items()):
        record=records[key]
        if record['id']!=key:raise ValueError('record ID mismatch')
        classification=parser.score(record['output'],item['expected'],technical_complete=key not in failed_ids)
        output.append({'id':key,'case':item['case'],'family':item['family'],'condition':item['condition'],
                       'reference':item['expected'],'output':record['output'],'classification':classification})
    if len(output)!=24:raise ValueError('expected 24 inputs')
    summary={}
    for family in ('number','category'):
        for condition in ('dual_sources','dual_alternatives'):
            group=[x for x in output if x['family']==family and x['condition']==condition]
            summary[f'{family}/{condition}']={'n':len(group),'counts':dict(collections.Counter(x['classification'] for x in group))}
    return output,summary
