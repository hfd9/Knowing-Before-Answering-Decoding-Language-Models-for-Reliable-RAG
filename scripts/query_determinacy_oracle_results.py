#!/usr/bin/env python3
"""Verify saved oracle-world results and replay the frozen evaluator."""
import csv
import hashlib
import json
from pathlib import Path

import query_determinacy_oracle_evaluate as evaluator
import query_determinacy_oracle_parser as parser
import query_determinacy_oracle_run as run

ROOT=run.ROOT
RESULT=ROOT/'docs/review/2026-11-15-query-determinacy-oracle-results-v1'


def analyze():
    archive=json.loads((RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    if len(archive)!=289 or len({x['path'] for x in archive})!=289:raise ValueError('source count mismatch')
    for entry in archive:
        raw=entry['raw_utf8'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=entry['sha256'] or (ROOT/entry['path']).read_bytes()!=raw:
            raise ValueError('source file differs: '+entry['path'])
    records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in archive if '/records/' in x['path'])}
    attempts=[json.loads(x['raw_utf8']) for x in archive if '/attempts/' in x['path']]
    if len(records)!=144 or len(attempts)!=144:raise ValueError('unexpected record count')
    if any('/automatic_failures/' in x['path'] for x in archive):raise ValueError('unexpected failure receipt')
    data=run.inputs();rows,summary=evaluator.evaluate(data,records,set())
    with (RESULT/'pairs.csv').open(encoding='utf-8',newline='') as f:saved=list(csv.DictReader(f))
    if saved!=rows or summary!=json.loads((RESULT/'summary.json').read_text(encoding='utf-8')):
        raise ValueError('saved pair data or summary differs')
    with (RESULT/'parsed-inputs.csv').open(encoding='utf-8',newline='') as f:parsed=list(csv.DictReader(f))
    if len(parsed)!=144 or {x['id'] for x in parsed}!=set(data):raise ValueError('parsed item count mismatch')
    for row in parsed:
        r=records[row['id']];item=data[row['id']]
        if int(row['index'])!=r['index'] or row['raw']!=r['output'] or row['parsed']!=parser.parse(r['output']):
            raise ValueError('parsed item differs')
        if row['reference']!=item['expected'] or any(row[k]!=item[k] for k in ('case','query','family','condition')):
            raise ValueError('metadata differs')
    return {'source_files':len(archive),'records':len(records),'questions':len(rows),
            'parsed_inputs':len(parsed),'invalid_formats':sum(x['parsed']=='X' for x in parsed),'summary':summary}


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,sort_keys=True,indent=2))
