#!/usr/bin/env python3
"""Verify exact source files and replay fixed world-extraction scoring."""
import hashlib
import json
from pathlib import Path

import query_determinacy_world_extract_evaluate as evaluator
import query_determinacy_world_extract_run as run

ROOT=run.ROOT
RESULT=ROOT/'docs/review/2026-11-15-query-determinacy-world-extract-results-v1'


def analyze():
    sources=json.loads((RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    if len(sources)!=49 or len({x['path'] for x in sources})!=49:raise ValueError('source count')
    for x in sources:
        raw=x['raw_utf8'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=x['sha256'] or (ROOT/x['path']).read_bytes()!=raw:
            raise ValueError('source mismatch: '+x['path'])
    if any('/automatic_failures/' in x['path'] for x in sources):raise ValueError('unexpected technical failure')
    records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in sources if '/records/' in x['path'])}
    attempts=[x for x in sources if '/attempts/' in x['path']]
    if len(records)!=24 or len(attempts)!=24:raise ValueError('record or attempt count')
    rows,summary=evaluator.evaluate(run.inputs(),records,set())
    if rows!=json.loads((RESULT/'items.json').read_text(encoding='utf-8')) or summary!=json.loads((RESULT/'summary.json').read_text(encoding='utf-8')):
        raise ValueError('frozen evaluation does not match saved results')
    return {'source_files':len(sources),'records':len(records),'items':len(rows),'summary':summary}


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,sort_keys=True,indent=2))
