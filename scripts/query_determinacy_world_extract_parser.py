#!/usr/bin/env python3
"""Frozen JSON-array extraction parser and reference comparison."""
import json


def parse(output,technical_complete=True):
    if not technical_complete:return ('T',None)
    if not isinstance(output,str):raise ValueError('output must be text')
    try:value=json.loads(output)
    except (json.JSONDecodeError,TypeError):return ('invalid',None)
    if type(value) is not list or len(value)!=2 or any(type(x) is not str or not x for x in value) or value[0]==value[1]:
        return ('invalid',None)
    return ('parsed',value)


def score(output,expected,technical_complete=True):
    if type(expected) is not list or len(expected)!=2 or any(type(x) is not str for x in expected) or expected[0]==expected[1]:
        raise ValueError('invalid reference')
    status,value=parse(output,technical_complete)
    if status!='parsed':return status
    if value==expected:return 'exact_order'
    if value==list(reversed(expected)):return 'correct_reversed'
    return 'incorrect'
