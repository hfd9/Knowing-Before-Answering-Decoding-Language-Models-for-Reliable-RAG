#!/usr/bin/env python3
"""Frozen parser for a proposed finite-world development comparison.

This module does not authorize or run a model. The caller must preserve the
original response and choose the value domain from the material, not a label.
"""
import json
import re

MAX_OUTPUT_CHARS = 4096
MAX_INTEGER = 999_999_999
INTEGER = re.compile(r'(?:0|[1-9][0-9]{0,8})\Z', re.ASCII)
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z', re.ASCII)


class _JsonInteger(str):
    """Keep a JSON integer's literal spelling without integer conversion."""


def _reject_number(_value):
    raise ValueError('non-integer number')


def parse(output, domain, technical_complete=True):
    """Return status, normalized strings and source types; never use reference values.

    integer: canonical nonnegative integers <= MAX_INTEGER, either JSON integers
    or canonical digit strings. identifier: case-sensitive ASCII strings only.
    Fail closed on malformed, ambiguous, duplicate or unsupported responses.
    """
    if domain not in ('integer', 'identifier'):
        raise ValueError('unknown domain')
    if not technical_complete:
        return {'status': 'technical_failure', 'values': None, 'types': None}
    if not isinstance(output, str):
        raise TypeError('output must be text')
    invalid = {'status': 'invalid', 'values': None, 'types': None}
    if len(output) > MAX_OUTPUT_CHARS:
        return invalid
    try:
        raw = json.loads(output, parse_int=_JsonInteger, parse_float=_reject_number,
                         parse_constant=_reject_number)
    except (ValueError, RecursionError):
        return invalid
    if type(raw) is not list or len(raw) != 2:
        return invalid
    values, types = [], []
    for value in raw:
        if type(value) is _JsonInteger:
            kind = 'json_integer'
        elif type(value) is str:
            kind = 'string'
        else:
            return invalid
        if domain == 'integer':
            if not INTEGER.fullmatch(value):
                return invalid
        elif kind != 'string' or not IDENTIFIER.fullmatch(value):
            return invalid
        values.append(str(value))
        types.append(kind)
    if values[0] == values[1]:
        return invalid
    return {'status': 'parsed', 'values': values, 'types': types}
