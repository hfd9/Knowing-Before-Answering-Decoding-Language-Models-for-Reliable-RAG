#!/usr/bin/env python3
"""Candidate pair flags for later development-only triage; no files are opened.

Neither non-matches nor short inputs demonstrate novelty. This module cannot
authorize access to held-out text and is not a semantic similarity detector.
"""
import unicodedata

MIN_LENGTH = 16
NGRAM = 8


def normalize(text):
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    value = ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())
    if not value:
        raise ValueError('text has no comparable characters')
    return value


def compare(candidate, reference):
    """Flag exact, long containment and >=80% distinct 8-character overlap."""
    a, b = normalize(candidate), normalize(reference)
    short = min(len(a), len(b)) < MIN_LENGTH
    exact = a == b
    if short:
        return {'exact': exact, 'short': True, 'containment': None, 'near': None}
    left = {a[i:i + NGRAM] for i in range(len(a) - NGRAM + 1)}
    right = {b[i:i + NGRAM] for i in range(len(b) - NGRAM + 1)}
    # Compare distinct n-grams against the shorter set without floating-point rounding.
    near = len(left & right) * 5 >= 4 * min(len(left), len(right))
    return {'exact': exact, 'short': False, 'containment': a in b or b in a, 'near': near}
