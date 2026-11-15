#!/usr/bin/env python3
"""Frozen deterministic parser for the formatted prospective development test."""


def parse(output,technical_complete=True):
    if not technical_complete:return 'T'
    if not isinstance(output,str):raise ValueError('output must be text')
    text=output.strip()
    if text and text[-1] in '。.!！':text=text[:-1].rstrip()
    return {'是':'Y','否':'N','无法确定':'U'}.get(text,'X')


def combine(a,b):
    if a not in ('Y','N','U','X','T') or b not in ('Y','N','U','X','T'):
        raise ValueError('invalid branch status')
    if 'T' in (a,b):return 'T'
    if a not in ('Y','N') or b not in ('Y','N'):return 'X'
    return a if a==b else 'U'
