"""Check report links and selected counts against existing project artifacts; CPU only."""
import collections
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
def read(relative): return json.loads((ROOT / relative).read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

report = HERE / 'README.md'
links = re.findall(r'\]\(([^)]+)\)', report.read_text(encoding='utf-8'))
local = [link for link in links if not re.match(r'^[a-z]+://', link)]
for link in local:
    assert (HERE / link.split('#',1)[0]).exists(), link
paths = [
 'docs/review/2026-11-09-probe-measurement-scope-decision-v1/measurement-summary.csv',
 'docs/review/2026-11-09-probe-neutral-control-results-v1/summary.json',
 'docs/review/2026-11-09-cli-probe-comparison-v1/summary.json',
 'docs/review/2026-11-11-new-controlled-exploration-results-v1/source/states.json',
 'docs/review/2026-11-11-controlled-probe-interpretation-v1/pairs.csv',
 'docs/review/2026-11-07-e1-user-results-v1/analysis-v2/summary.json',
 'docs/review/2026-11-09-probe-research-decision-v1/README.md',
 'docs/records/2026-11-11-faitheval-four-step.md',
 'docs/review/2026-11-09-probe-measurement-scope-decision-v1/paired-summary.csv',
]
with (ROOT/paths[0]).open(encoding='utf-8',newline='') as f: m=list(csv.DictReader(f))
for v in ('v1','v2'):
    row=next(r for r in m if r['task']=='binding48' and r['condition']=='I' and r['expression']==v)
    assert (int(row['inputs']),int(row['pred_answer']),int(row['pred_refuse']))==(12,12,0)
for v in ('A','B'):
    row=next(r for r in m if r['task']=='transfer240' and r['condition']=='I' and r['expression']==v)
    assert (int(row['inputs']),int(row['pred_refuse']))==(30,8)
with (ROOT/paths[8]).open(encoding='utf-8',newline='') as f: paired=list(csv.DictReader(f))
row=next(r for r in paired if r['task']=='transfer240' and r['condition']=='I')
assert (int(row['bases']),int(row['both_match']))==(30,7)
neutral=read(paths[1])
assert round(neutral['groups']['D']['negative_minus_neutral_pp']['mean'],2)==2.68
assert round(neutral['groups']['P']['negative_minus_neutral_pp']['mean'],2)==6.56
cli=read(paths[2])
assert cli['by_condition']['I']['probe']=={'answer':15,'refuse':2,'conflict':9}
assert cli['by_condition']['S']['probe']=={'answer':13,'conflict':13}
assert cli['paired_both_match_CLI']==1 and cli['S_I_pairs']==26 and cli['linked_author_CLI_disagreements']==9
new=read(paths[3])['records'][1:]
assert len(new)==36
assert {s:dict(collections.Counter(r['probe_pred'] for r in new if r['document_level']==s)) for s in 'SIC'} == {
 'S':{'answer':9,'conflict':3},'I':{'answer':4,'conflict':8},'C':{'conflict':12}}
with (ROOT/paths[4]).open(encoding='utf-8',newline='') as f: pairs=list(csv.DictReader(f))
assert len(pairs)==42
for typ, cls, expected in [('S-I','refuse',2.99),('S-C','conflict',50.86)]:
    values=[float(r['delta_'+cls])*100 for r in pairs if r['comparison']==typ]
    assert len(values)==12 and all(v>0 for v in values) and round(sum(values)/12,2)==expected
e1=read(paths[5])['conditions']
for cond, w in [('I0',(3,5,4)),('IU',(5,4,3))]:
    endpoints=e1[cond]['endpoints']
    x=endpoints['unsupported_target_conflict']
    assert (x['yes'],x['no'],x['explicit_reviewed_unknown'])==(0,12,0)
    x=endpoints['withholds_target_with_support']
    assert (x['yes'],x['no'],x['explicit_reviewed_unknown'])==w
print(json.dumps({'status':'passed','local_links_checked':len(local),
 'checks':'transfer, binding, neutral, CLI, new probe and E1 selected counts; all references exist',
 'limitations':'Checks selected counts and paths, not semantic accuracy, sample independence, source entirety or runtime provenance.',
 'report_sha256':sha(report),'source_sha256':{p:sha(ROOT/p) for p in paths}},ensure_ascii=False,indent=2))
