"""Archive and replay the completed matched-length control without new inference."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import pickle

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/qwen2.5-3b-probe-neutral-length-control-20261109-v1'
OLD=ROOT/'runs/qwen2.5-3b-probe-support-expression-v1'
PROBE=ROOT/'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'
OUT=ROOT/'docs/review/2026-11-09-probe-neutral-control-results-v1'
MODES=('answer','refuse','conflict')


def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def archive():
    comparisons=read(RUN/'materials/comparisons.json')
    state=read(OLD/'states.json'); old_by={r['id']:r for r in state['records']}
    old_ids={c[k] for c in comparisons for k in ('positive_id','negative_id')}
    assert len(old_ids)==24 and len(comparisons)==12
    paths=[]
    for name in ['protocol.json','materials/inputs.json','materials/comparisons.json','states.json','report.json']:
        paths.append((RUN/name,OUT/'source/new'/name))
    for part in ('attempts','features'):
        expected=[f'{i:04d}.json' if part=='attempts' else f'{i:04d}.npy' for i in range(13)]
        assert {p.name for p in (RUN/part).iterdir()}==set(expected)
        paths.extend((RUN/part/name,OUT/'source/new'/part/name) for name in expected)
    for name in ['protocol.json','states.json','materials/inputs.json']:
        paths.append((OLD/name,OUT/'source/old'/name))
    for name in sorted({old_by[x]['feature_file'] for x in old_ids}):
        paths.append((OLD/name,OUT/'source/old'/name))
    paths.append((PROBE,OUT/'source/old/probe.pkl'))
    assert len(paths)==59 and len({str(dst) for _,dst in paths})==59
    assert not (OUT/'source-manifest.json').exists(), 'refuse to replace existing source archive'
    inventory=[]
    for original,dest in paths:
        raw=original.read_bytes(); dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f: f.write(raw)
        inventory.append({'source_path':str(original.relative_to(ROOT)), 'archive_path':str(dest.relative_to(ROOT)),
                          'bytes':len(raw),'sha256':sha(raw)})
    with (OUT/'source-manifest.json').open('xb') as f:
        f.write(encoded({'format':'neutral-control-archive-v1','files':inventory,'new_forward_records':13,
                         'old_endpoint_features':24,'probe_pickle_is_trusted_project_artifact':True}))
    return len(inventory)


def verify_sources():
    manifest=read(OUT/'source-manifest.json'); entries=manifest['files']
    assert len(entries)==59 and len({r['archive_path'] for r in entries})==59
    live_matches=0; missing=[]
    for x in entries:
        b=(ROOT/x['archive_path']).read_bytes()
        assert len(b)==x['bytes'] and sha(b)==x['sha256']
        path=ROOT/x['source_path']
        if path.exists():
            assert sha(path.read_bytes())==x['sha256']; live_matches+=1
        else: missing.append(x['source_path'])
    return live_matches,missing


def csv_bytes(rows):
    f=io.StringIO(newline=''); w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return f.getvalue().encode()


def analysis():
    live_matches,missing=verify_sources()
    base=OUT/'source'; new=base/'new'; old=base/'old'
    protocol=read(new/'protocol.json'); records=read(new/'states.json')['records']
    old_records=read(old/'states.json')['records']; old_by={r['id']:r for r in old_records}
    new_by={r['id']:r for r in records}; comparisons=read(new/'materials/comparisons.json')
    assert len(records)==len(new_by)==13 and len(comparisons)==12
    probe_path=old/'probe.pkl'
    assert sha(probe_path.read_bytes())==protocol['source_probe_sha256']
    probe=pickle.loads(probe_path.read_bytes()); cal=probe['router'].calibrated_classifiers_[0]
    coef=cal.estimator.coef_; intercept=cal.estimator.intercept_
    a=np.array([c.a_ for c in cal.calibrators]); b=np.array([c.b_ for c in cal.calibrators])
    def compute(record,directory):
        raw=(directory/record['feature_file']).read_bytes(); assert sha(raw)==record['feature_sha256']
        values=np.load(io.BytesIO(raw),allow_pickle=False)
        assert values.shape==(36,2048) and values.dtype==np.float16 and np.isfinite(values).all()
        x=values[28][None].astype(np.float32); x-=probe['scaler'].mean_; x/=probe['scaler'].scale_
        score=(x@coef.T+intercept)[0]; sigmoid=1/(1+np.exp(a*score+b)); prob=sigmoid/sigmoid.sum()
        assert MODES[int(np.argmax(prob))]==record['probe_pred']
        assert max(abs(float(prob[i])-record['probe_probabilities'][m]) for i,m in enumerate(MODES))<1e-10
        return score,prob
    pairs=[]; cells=[]
    report={p['neutral_id']:p for p in read(new/'report.json')['pairs']}
    for cmp in comparisons:
        ids={'positive':cmp['positive_id'],'negative':cmp['negative_id'],'neutral':cmp['neutral_id']}
        vals={}
        for cond,id_ in ids.items():
            record=(new_by if cond=='neutral' else old_by)[id_]
            score,prob=compute(record,new if cond=='neutral' else old)
            vals[cond]=(record,score,prob)
            cells.append(dict(base=cmp['base'],wording=cmp['wording'],condition=cond,id=id_,
                              input_tokens=record['input_tokens'],prediction=record['probe_pred'],
                              p_answer=float(prob[0]),p_refuse=float(prob[1]),p_conflict=float(prob[2]),
                              raw_linear_answer=float(score[0]),raw_linear_refuse=float(score[1]),
                              raw_linear_conflict=float(score[2]),feature_sha256=record['feature_sha256']))
        p0,p1,pn=(vals[c][2] for c in ('positive','negative','neutral'))
        s0,s1,sn=(vals[c][1] for c in ('positive','negative','neutral'))
        saved=report[cmp['neutral_id']]
        assert abs(float(p1[2]-pn[2])-saved['negative_minus_neutral_conflict'])<1e-10
        assert vals['negative'][0]['input_tokens']==vals['neutral'][0]['input_tokens']
        pairs.append(dict(base=cmp['base'],wording=cmp['wording'],positive_id=ids['positive'],
                          negative_id=ids['negative'],neutral_id=ids['neutral'],
                          positive_tokens=vals['positive'][0]['input_tokens'],
                          negative_tokens=vals['negative'][0]['input_tokens'],neutral_tokens=vals['neutral'][0]['input_tokens'],
                          positive_pred=vals['positive'][0]['probe_pred'],negative_pred=vals['negative'][0]['probe_pred'],
                          neutral_pred=vals['neutral'][0]['probe_pred'],
                          positive_p_conflict=float(p0[2]),negative_p_conflict=float(p1[2]),neutral_p_conflict=float(pn[2]),
                          negative_minus_neutral_pp=float(100*(p1[2]-pn[2])),
                          negative_minus_positive_pp=float(100*(p1[2]-p0[2])),
                          neutral_minus_positive_pp=float(100*(pn[2]-p0[2])),
                          negative_minus_neutral_raw_conflict_score=float(s1[2]-sn[2]),
                          negative_minus_positive_raw_conflict_score=float(s1[2]-s0[2]),
                          neutral_minus_positive_raw_conflict_score=float(sn[2]-s0[2])))
    assert len(pairs)==12 and len(cells)==36 and len({(r['base'],r['wording']) for r in pairs})==12
    groups={}
    for wording in ('D','P'):
        rows=[r for r in pairs if r['wording']==wording]; assert len(rows)==6
        out={'pairs':6}
        for name in ('negative_minus_neutral_pp','negative_minus_positive_pp','neutral_minus_positive_pp',
                     'negative_minus_neutral_raw_conflict_score'):
            v=[r[name] for r in rows]
            out[name]={'mean':sum(v)/len(v),'minimum':min(v),'maximum':max(v),
                       'positive':sum(x>0 for x in v),'negative':sum(x<0 for x in v),'zero':sum(x==0 for x in v)}
        out['negative_vs_neutral_class_changes']=sum(r['negative_pred']!=r['neutral_pred'] for r in rows)
        out['positive_to_negative_class_changes']=sum(r['positive_pred']!=r['negative_pred'] for r in rows)
        out['positive_to_neutral_class_changes']=sum(r['positive_pred']!=r['neutral_pred'] for r in rows)
        out['class_counts']={cond:dict(Counter(r[cond+'_pred'] for r in rows)) for cond in ('positive','negative','neutral')}
        groups[wording]=out
    summary={'status':'completed_exposed_development_diagnostic_not_semantic_gold',
             'source_archive_files':59,'source_live_files_matched':live_matches,'source_live_files_missing':missing,
             'new_forwards':13,'new_neutral_inputs':12,'bridge_inputs':1,'original_bases':6,
             'new_answers':0,'new_fits':0,'new_independent_semantic_labels':0,'groups':groups,
             'raw_linear_scores_status':'posthoc_offline_exact_frozen_probe_calculation_no_new_fitting_or_threshold',
             'interpretation':read(new/'report.json')['interpretation']}
    return {'cells.csv':csv_bytes(cells),'pairs.csv':csv_bytes(pairs),'summary.json':encoded(summary)}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--stage',required=True,choices=['archive','analyze','verify']); args=p.parse_args()
    if args.stage=='archive': print(json.dumps({'status':'archived','files':archive()})); return
    out=analysis()
    for name,data in out.items():
        path=OUT/name
        if args.stage=='analyze':
            with path.open('xb') as f: f.write(data)
        else: assert path.read_bytes()==data,name
    print(json.dumps({'status':'ok','stage':args.stage,'rows':36,'pairs':12,'archived_sources':59}))


if __name__=='__main__': main()
