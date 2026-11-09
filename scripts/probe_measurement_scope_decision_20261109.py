"""Reorganize previously published probe tables for an exposed-reference scope decision."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-09-probe-measurement-scope-decision-v1'
SOURCES={
 'corpus':'docs/review/2026-11-09-probe-existing-cache-audit-v1/corpus.csv',
 'ab':'docs/review/2026-11-09-probe-existing-cache-audit-v1/AB_pairs.csv',
 'neutral':'docs/review/2026-11-09-probe-neutral-control-results-v1/cells.csv',
 'neutral_report':'docs/review/2026-11-09-probe-neutral-control-results-v1/README.md',
 'neutral_reference':'docs/records/2026-10-20-probe-support-expression-preparation.md',
 'binding_reference':'docs/records/2026-10-21-behavior-binding-probe-results.md',
}
CLASSES=('answer','refuse','conflict')


def rows(name):
    with (ROOT/SOURCES[name]).open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))


def table_bytes(table):
    f=io.StringIO(newline=''); w=csv.DictWriter(f,fieldnames=list(table[0]),lineterminator='\n');w.writeheader();w.writerows(table)
    return f.getvalue().encode('utf-8')


def build():
    corpus=rows('corpus'); ab=rows('ab'); neutral=rows('neutral')
    transfer=[r for r in corpus if r['dataset']=='transfer240']; binding=[r for r in corpus if r['dataset']=='binding48']
    assert len(transfer)==240 and len(binding)==48 and len(neutral)==36 and len(ab)==120
    assert len({r['id'] for r in transfer})==240 and len({r['id'] for r in binding})==48
    assert len({(r['base'],r['wording'],r['condition']) for r in neutral})==36
    assert all(r['formal_label']=='' and r['state_timing']=='generation_prefill' for r in transfer)
    assert all(r['formal_label']=='' and r['state_timing']=='post_answer_recomputed' for r in binding)
    assert sum(r['author_reference']=='unknown' for r in transfer)==4
    cells=[]
    for r in transfer:
        cells.append(dict(task='transfer240',base=r['original_id'],input_id=r['id'],condition=r['condition'],
                          expression=r['expression'],author_reference=r['author_reference'],prediction=r['calibrated_pred']))
    for r in binding:
        cells.append(dict(task='binding48',base=r['original_id'],input_id=r['id'],condition=r['condition'],
                          expression=r['variant'],author_reference=r['author_reference'],prediction=r['calibrated_pred']))
    for r in neutral:
        cells.append(dict(task='neutral_control',base=r['base'],input_id=r['id'],condition=r['condition'],
                          expression=r['wording'],author_reference='answer',prediction=r['prediction']))
    assert all(c['prediction'] in CLASSES and c['author_reference'] in CLASSES+('unknown',) for c in cells)
    grouped=[]
    keys=('task','condition','expression','author_reference')
    for key in sorted({tuple(c[k] for k in keys) for c in cells}):
        sel=[c for c in cells if tuple(c[k] for k in keys)==key]; ref=key[-1]; count=Counter(c['prediction'] for c in sel)
        grouped.append(dict(zip(keys,key),inputs=len(sel),bases=len({c['base'] for c in sel}),
                            pred_answer=count['answer'],pred_refuse=count['refuse'],pred_conflict=count['conflict'],
                            match_reference=sum(c['prediction']==ref for c in sel) if ref!='unknown' else '',
                            not_match_reference=sum(c['prediction']!=ref for c in sel) if ref!='unknown' else '',
                            author_reference_unknown=len(sel) if ref=='unknown' else 0))
    pairs=[]
    for p in ab:
        pairs.append(dict(task='transfer240',base=p['original_id'],condition=p['contrast'].split('_')[-1],
                          left_id=p['left_id'],right_id=p['right_id'],left_expression='A',right_expression='B',
                          left_reference=p['left_reference'],right_reference=p['right_reference'],
                          left_pred=p['left_calibrated_pred'],right_pred=p['right_calibrated_pred'],
                          class_same=p['calibrated_class_same']=='True',author_acceptance=p['author_acceptance_status']))
    for condition in ('S','I'):
        bases=sorted({r['original_id'] for r in binding if r['condition']==condition})
        for base in bases:
            a=[r for r in binding if r['original_id']==base and r['condition']==condition and r['variant']=='v1']
            b=[r for r in binding if r['original_id']==base and r['condition']==condition and r['variant']=='v2']
            assert len(a)==len(b)==1
            a,b=a[0],b[0]
            pairs.append(dict(task='binding48',base=base,condition=condition,left_id=a['id'],right_id=b['id'],
                              left_expression='v1',right_expression='v2',left_reference=a['author_reference'],right_reference=b['author_reference'],
                              left_pred=a['calibrated_pred'],right_pred=b['calibrated_pred'],
                              class_same=a['calibrated_pred']==b['calibrated_pred'],author_acceptance='author_construction'))
    for condition in ('positive','negative','neutral'):
        bases=sorted({r['base'] for r in neutral if r['condition']==condition})
        for base in bases:
            a=[r for r in neutral if r['base']==base and r['condition']==condition and r['wording']=='D']
            b=[r for r in neutral if r['base']==base and r['condition']==condition and r['wording']=='P']
            assert len(a)==len(b)==1
            a,b=a[0],b[0]
            pairs.append(dict(task='neutral_control',base=base,condition=condition,left_id=a['id'],right_id=b['id'],
                              left_expression='D',right_expression='P',left_reference='answer',right_reference='answer',
                              left_pred=a['prediction'],right_pred=b['prediction'],class_same=a['prediction']==b['prediction'],
                              author_acceptance='exposed_supported_core_with_format_or_redundant_suffix_not_independent'))
    assert Counter(p['task'] for p in pairs)=={'transfer240':120,'binding48':24,'neutral_control':18}
    pair_summary=[]
    for task,condition in sorted({(p['task'],p['condition']) for p in pairs}):
        selected=[p for p in pairs if p['task']==task and p['condition']==condition]
        counts=Counter()
        for p in selected:
            if p['left_reference']=='unknown' or p['right_reference']=='unknown': counts['unknown']+=1; continue
            left=p['left_pred']==p['left_reference']; right=p['right_pred']==p['right_reference']
            counts['both' if left and right else 'left_only' if left else 'right_only' if right else 'neither']+=1
        pair_summary.append(dict(task=task,condition=condition,pairs=len(selected),bases=len({p['base'] for p in selected}),
                                 class_same=sum(p['class_same'] for p in selected),class_changed=sum(not p['class_same'] for p in selected),
                                 both_match=counts['both'],left_only=counts['left_only'],right_only=counts['right_only'],
                                 neither_match=counts['neither'],unknown=counts['unknown']))
    meta={'status':'retrospective_exposed_author_reference_not_gold',
          'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCES.values()},
          'input_counts':{'transfer240':240,'binding48':48,'neutral_control':36},
          'base_counts':{'transfer240':30,'binding48':12,'neutral_control':6},
          'neutral_control_overlap':'24 positive/negative rows are old cached inputs; only 12 neutral inputs are new; never pool as independent samples.',
          'pair_counts':{'transfer240':120,'binding48':24,'neutral_control':18},
          'formal_labels_assigned':0,'semantic_gold':False,'gpu_calls':0,'forwards':0,'new_fits':0}
    return {'measurement-summary.csv':table_bytes(grouped),'paired-summary.csv':table_bytes(pair_summary),
            'paired-items.csv':table_bytes(pairs),'provenance.json':(json.dumps(meta,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--stage',required=True,choices=['analyze','verify']); a=p.parse_args()
    data=build(); OUT.mkdir(parents=True,exist_ok=True)
    for name,raw in data.items():
        path=OUT/name
        if a.stage=='analyze':
            with path.open('xb') as f:f.write(raw)
        else: assert path.read_bytes()==raw,name
    print(json.dumps({'status':'ok','stage':a.stage,'group_rows':len(list(csv.DictReader(io.StringIO(data['measurement-summary.csv'].decode())))),
                      'paired_rows':162,'gpu_calls':0,'new_fits':0}))


if __name__=='__main__': main()
