"""Independent manual CPU replay of the saved288 linear/calibration diagnostic rows."""

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import pickle

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/qwen2.5-3b-probe-calibration-diagnostic-v1'
PREFIX=ROOT/'docs/records/2026-10-21-probe-calibration-diagnostic'
MODES=['answer','refuse','conflict']
DISPOSITIONS=['unchanged_correct','unchanged_wrong','changed_corrected','changed_damaged',
              'changed_both_wrong','changed_reference_unknown','unchanged_reference_unknown']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest):
    for name,value in manifest.items():
        assert sha(ROOT/name)==value,name


def rate(values):
    n=len(values);counts=Counter(values)
    return dict(eligible=n,yes=counts['yes'],no=counts['no'],unknown=counts['unknown'],
        point=counts['yes']/n if n and not counts['unknown'] else None,
        lower=counts['yes']/n if n else None,upper=(counts['yes']+counts['unknown'])/n if n else None)


def summary(rows):
    known=[r for r in rows if r['author_reference'] in MODES]
    result=dict(rows=len(rows),bases=len({r['original_id'] for r in rows}),known_reference=len(known),
        unknown_reference=len(rows)-len(known),class_changes=sum(r['raw_pred']!=r['calibrated_pred'] for r in rows),
        dispositions={k:sum(r['disposition']==k for r in rows) for k in DISPOSITIONS},
        transitions={a:{b:sum(r['raw_pred']==a and r['calibrated_pred']==b for r in rows) for b in MODES} for a in MODES})
    for stage in ['raw','calibrated']:
        result[stage]=dict(matches_author_reference=sum(r[stage+'_pred']==r['author_reference'] for r in known),
            distribution={m:sum(r[stage+'_pred']==m for r in rows) for m in MODES},
            confusion={a:{b:sum(r['author_reference']==a and r[stage+'_pred']==b for r in known) for b in MODES} for a in MODES},
            I_existing_answer_by_class={m:rate([r['existing_has_answer'] for r in rows if r['author_reference']=='refuse'
                and r[stage+'_pred']==m]) for m in MODES})
    result['net_reference_matches']=result['calibrated']['matches_author_reference']-result['raw']['matches_author_reference']
    return result


def main():
    preservation=read(Path(str(PREFIX)+'-preserved.json'))
    run_manifest=read(Path(str(PREFIX)+'-run-hashes.json'))
    check(preservation);check(run_manifest)
    assert {str(p.relative_to(ROOT)) for p in RUN.rglob('*') if p.is_file()}==set(run_manifest)
    spec=read(ROOT/'prompts/probe_calibration_diagnostic_v1.json')
    path=ROOT/spec['probe_source']
    assert sha(path)==spec['probe_sha256']=='db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
    probe=pickle.loads(path.read_bytes());cal=probe['router'].calibrated_classifiers_[0]
    coef=cal.estimator.coef_;intercept=cal.estimator.intercept_
    a=np.array([c.a_ for c in cal.calibrators]);b=np.array([c.b_ for c in cal.calibrators])
    rows=read(RUN/'rows.json');report=read(RUN/'report.json')
    assert len(rows)==len({(r['dataset'],r['id']) for r in rows})==288
    indexed={};originals={}
    for dataset,ds in spec['datasets'].items():
        run=ROOT/ds['run'];records=read(run/ds['records'])['records']
        indexed[dataset]={r['id']:r for r in records}
        if dataset=='binding48':
            originals[dataset]={r['id']:r for r in read(run/ds['behavior'])}
        else:
            with (ROOT/ds['behavior']).open(newline='') as stream:
                originals[dataset]={r['id']:r for r in csv.DictReader(stream)}
    errors={k:0. for k in ['linear','raw_softmax','sigmoid_logit','sigmoid_unnormalized','calibrated_p','original_saved_probability']}
    for row in rows:
        dataset=row['dataset'];record=indexed[dataset][row['id']];original=originals[dataset][row['id']]
        path=ROOT/spec['datasets'][dataset]['run']/record['feature_file']
        assert sha(path)==record['feature_sha256']==row['feature_sha256']
        values=np.load(path,allow_pickle=False)
        assert values.shape==(36,2048) and values.dtype==np.float16
        assert np.isfinite(values).all() and not np.any(np.all(values==0,axis=1))
        x=values[28][None].astype(np.float32)
        x-=probe['scaler'].mean_;x/=probe['scaler'].scale_
        score=(x@coef.T+intercept)[0]
        softmax=np.exp(score-score.max());softmax/=softmax.sum()
        logit=-(a*score+b)
        sigmoid=1/(1+np.exp(-logit));prob=sigmoid/sigmoid.sum()
        assert row['raw_pred']==MODES[int(np.argmax(score))]
        assert row['calibrated_pred']==record['probe_pred']==MODES[int(np.argmax(prob))]
        assert np.argmax(sigmoid)==np.argmax(prob)
        for key,value in [('linear',score),('raw_softmax',softmax),('sigmoid_logit',logit),
                          ('sigmoid_unnormalized',sigmoid),('calibrated_p',prob)]:
            error=max(abs(row[key+'_'+mode]-float(value[i])) for i,mode in enumerate(MODES))
            errors[key]=max(errors[key],error);assert error<1e-10
        error=max(abs(record['probe_probabilities'][mode]-prob[i]) for i,mode in enumerate(MODES))
        errors['original_saved_probability']=max(errors['original_saved_probability'],float(error));assert error<1e-10
        assert row['existing_behavior']=={f:original[f] for f in row['existing_behavior']}
        assert row['raw_output']==original['raw_output'] and row['question']==original['question']
        assert row['existing_has_answer']==original['has_substantive_target_answer' if dataset=='binding48' else 'has_substantive_answer']
        expected_ref=('answer' if row['condition']=='S' else 'refuse') if dataset=='binding48' else original['exposed_author_input_mode']
        assert row['author_reference']==expected_ref
        before,after=row['raw_pred']==expected_ref,row['calibrated_pred']==expected_ref
        changed=row['raw_pred']!=row['calibrated_pred']
        if expected_ref=='unknown':
            assert row['raw_matches_reference'] is None and row['calibrated_matches_reference'] is None
            expected='changed_reference_unknown' if changed else 'unchanged_reference_unknown'
        else:
            assert row['raw_matches_reference']==before and row['calibrated_matches_reference']==after
            expected=('changed_corrected' if after else 'changed_damaged' if before else 'changed_both_wrong') if changed else (
                'unchanged_correct' if before else 'unchanged_wrong')
        assert row['disposition']==expected
    assert sum(r['author_reference']=='unknown' for r in rows)==4
    assert sum(r['existing_behavior'].get('claimed_evidence_supports_target')=='unknown' for r in rows if r['dataset']=='binding48')==48
    for dataset in spec['datasets']:
        group=[r for r in rows if r['dataset']==dataset]
        assert len(group)==spec['datasets'][dataset]['rows']
        assert report['datasets'][dataset]==summary(group)
    slices=read(RUN/'slices.json');bases=read(RUN/'base_summaries.json')
    assert len(slices)==33 and len(bases)==42
    assert len({(r['dataset'],r['axis'],r['key']) for r in slices})==33
    for row in slices:
        selected=[r for r in rows if r['dataset']==row['dataset']]
        if row['axis'].startswith('partition_by_'):
            partition,value=row['key'].split('|');field=row['axis'].removeprefix('partition_by_')
            selected=[r for r in selected if r['partition']==partition and r[field]==value]
        elif row['axis']!='all':selected=[r for r in selected if r[row['axis']]==row['key']]
        assert {k:v for k,v in row.items() if k not in ['dataset','axis','key']}==summary(selected)
    for row in bases:
        selected=[r for r in rows if r['dataset']==row['dataset'] and r['original_id']==row['original_id']]
        assert {k:v for k,v in row.items() if k not in ['dataset','original_id']}==summary(selected)
    pairs=read(RUN/'pairs.json');by_id={(r['dataset'],r['id']):r for r in rows}
    assert len(pairs)==len({(r['dataset'],r['left_id'],r['right_id']) for r in pairs})==348
    for pair in pairs:
        left,right=[by_id[pair['dataset'],pair[side+'_id']] for side in ['left','right']]
        assert left['original_id']==right['original_id']==pair['original_id']
        assert left['partition']==right['partition']==pair['partition']
        assert pair['left_existing_behavior']==left['existing_behavior'] and pair['right_existing_behavior']==right['existing_behavior']
        if pair['contrast'].startswith('S_to_'):
            assert left['condition']=='S' and right['condition']==pair['contrast'][-1]
            assert left['expression']==right['expression'] and left['variant']==right['variant']
        elif pair['contrast'].startswith('distractor_'):
            assert left['variant']=='v1' and right['variant']=='v2' and left['condition']==right['condition']==pair['contrast'][-1]
        else:
            assert left['expression']=='A' and right['expression']=='B' and left['condition']==right['condition']==pair['contrast'][-1]
        for mode in MODES:
            for stage in ['linear','raw_softmax','calibrated_p']:
                assert pair['delta_'+stage+'_'+mode]==right[stage+'_'+mode]-left[stage+'_'+mode]
        for stage in ['raw','calibrated']:
            assert pair[stage+'_left_pred']==left[stage+'_pred'] and pair[stage+'_right_pred']==right[stage+'_pred']
            assert pair[stage+'_class_changed']==(left[stage+'_pred']!=right[stage+'_pred'])
            expected=None if 'unknown' in [left['author_reference'],right['author_reference']] else (
                left[stage+'_pred']==left['author_reference'] and right[stage+'_pred']==right['author_reference'])
            assert pair[stage+'_both_match_reference']==expected
    counts=Counter((p['dataset'],p['contrast']) for p in pairs)
    assert counts[('binding48','S_to_I')]==24 and counts[('binding48','distractor_I')]==counts[('binding48','distractor_S')]==12
    for condition in ['I','C','K']:assert counts[('transfer240','S_to_'+condition)]==60
    for condition in ['S','I','C','K']:assert counts[('transfer240','A_to_B_'+condition)]==30
    for name,values in [('rows',rows),('slices',slices),('pairs',pairs),('base_summaries',bases)]:
        buffer=io.StringIO(newline='');writer=csv.DictWriter(buffer,fieldnames=list(values[0]));writer.writeheader()
        writer.writerows([{k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v
            for k,v in row.items()} for row in values])
        assert (RUN/(name+'.csv')).read_bytes()==buffer.getvalue().encode()
        assert Path(str(PREFIX)+'-'+name+'.csv').read_bytes()==buffer.getvalue().encode()
    assert Path(str(PREFIX)+'.json').read_bytes()==(RUN/'report.json').read_bytes()
    assert report['new_fits']==report['new_gpu_calls']==report['new_answers']==report['thresholds_added']==0
    changed=[r for r in rows if r['raw_pred']!=r['calibrated_pred']]
    assert len(changed)==16 and all(r['calibrated_pred']=='conflict' for r in changed)
    for dataset in spec['datasets']:
        assert all(r['raw_pred']==r['calibrated_pred'] for r in rows if r['dataset']==dataset and r['condition']=='I')
    result=dict(status='independent_manual288_stage_and348_pair_replay_passed',independent_semantic_review=False,
        rows=288,pairs=348,slices=33,base_summaries=42,unknown_author_references_preserved=4,
        binding_citation_unknowns_preserved=48,preserved_paths=len(preservation),new_run_files=len(run_manifest),
        manual_stage_max_absolute_errors=errors,total_class_changes=16,all_changes_into_conflict=True,
        I_class_changes_by_dataset={d:0 for d in spec['datasets']},
        datasets={k:dict(known=v['known_reference'],unknown=v['unknown_reference'],before=v['raw']['matches_author_reference'],
            after=v['calibrated']['matches_author_reference'],changes=v['class_changes'],dispositions=v['dispositions']) for k,v in report['datasets'].items()},
        new_gpu_calls=0,new_answers=0,new_fits=0,new_behavior_ratings=0,thresholds_added=0,
        implementation_sha256=sha(Path(__file__)),source_run_manifest_sha256=sha(Path(str(PREFIX)+'-run-hashes.json')))
    check(preservation);check(run_manifest)
    target=Path(str(PREFIX)+'-verification.json');data=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    if target.exists():assert target.read_bytes()==data
    else:target.write_bytes(data)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
