"""Independently replay the 12 matched pairs using the archived frozen classifier."""
import csv
import hashlib
import json
from pathlib import Path
import pickle

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-09-probe-neutral-control-results-v1'
NEW=OUT/'source/new'; OLD=OUT/'source/old'
MODES=('answer','refuse','conflict')


def read(path): return json.loads(path.read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=read(OUT/'source-manifest.json'); assert len(manifest['files'])==59
    for r in manifest['files']:
        assert digest(ROOT/r['archive_path'])==r['sha256']
        assert digest(ROOT/r['source_path'])==r['sha256']
    probe_path=OLD/'probe.pkl'
    assert digest(probe_path)=='db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
    probe=pickle.loads(probe_path.read_bytes()); estimator=probe['router'].calibrated_classifiers_[0].estimator
    old={r['id']:r for r in read(OLD/'states.json')['records']}
    new={r['id']:r for r in read(NEW/'states.json')['records']}
    report={r['neutral_id']:r for r in read(NEW/'report.json')['pairs']}
    comparisons=read(NEW/'materials/comparisons.json')
    with (OUT/'cells.csv').open(newline='',encoding='utf-8') as f: cells=list(csv.DictReader(f))
    with (OUT/'pairs.csv').open(newline='',encoding='utf-8') as f: pairs=list(csv.DictReader(f))
    assert len(cells)==36 and len(pairs)==12 and len(comparisons)==12
    by_cell={(r['base'],r['wording'],r['condition']):r for r in cells}
    by_pair={(r['base'],r['wording']):r for r in pairs}
    assert len(by_cell)==36 and len(by_pair)==12
    max_probability_error=max_score_error=0.0
    for c in comparisons:
        pair=by_pair[c['base'],c['wording']]; saved=report[c['neutral_id']]
        probs={}; scores={}; classes={}
        for condition,k,records,directory in [('positive','positive_id',old,OLD),('negative','negative_id',old,OLD),('neutral','neutral_id',new,NEW)]:
            rec=records[c[k]]; cell=by_cell[c['base'],c['wording'],condition]
            assert cell['id']==c[k] and digest(directory/rec['feature_file'])==rec['feature_sha256']==cell['feature_sha256']
            values=np.load(directory/rec['feature_file'],allow_pickle=False)
            x=probe['scaler'].transform(values[28][None].astype(np.float32))
            score=estimator.decision_function(x)[0]; prob=probe['router'].predict_proba(x)[0]
            classes[condition]=MODES[int(np.argmax(prob))]; scores[condition]=score; probs[condition]=prob
            assert rec['probe_pred']==cell['prediction']==classes[condition]
            for i,m in enumerate(MODES):
                error=abs(float(cell['p_'+m])-float(prob[i])); max_probability_error=max(max_probability_error,error)
                score_error=abs(float(cell['raw_linear_'+m])-float(score[i])); max_score_error=max(max_score_error,score_error)
                assert error<1e-10 and score_error<1e-10
                assert abs(saved[condition+'_probabilities'][m]-float(prob[i]))<1e-10
            assert int(cell['input_tokens'])==rec['input_tokens']
        assert int(pair['negative_tokens'])==int(pair['neutral_tokens'])
        for name,one,two in [('negative_minus_neutral','negative','neutral'),('negative_minus_positive','negative','positive'),('neutral_minus_positive','neutral','positive')]:
            assert abs(float(pair[name+'_pp'])-100*(probs[one][2]-probs[two][2]))<1e-10
            assert abs(float(pair[name+'_raw_conflict_score'])-(scores[one][2]-scores[two][2]))<1e-10
        for condition in classes: assert pair[condition+'_pred']==classes[condition]
    summary=read(OUT/'summary.json')
    for wording in ('D','P'):
        group=[x for x in pairs if x['wording']==wording]; assert len(group)==6
        saved=summary['groups'][wording]
        assert saved['negative_vs_neutral_class_changes']==sum(x['negative_pred']!=x['neutral_pred'] for x in group)
        for name in ('negative_minus_neutral_pp','negative_minus_positive_pp','neutral_minus_positive_pp','negative_minus_neutral_raw_conflict_score'):
            values=[float(x[name]) for x in group]; actual=saved[name]
            assert abs(actual['mean']-sum(values)/6)<1e-10
            assert actual['positive']==sum(x>0 for x in values) and actual['negative']==sum(x<0 for x in values) and actual['zero']==sum(x==0 for x in values)
    print(json.dumps({'status':'independent_frozen_classifier_and_12_pair_analysis_verified',
      'archived_sources':59,'new_features':12,'old_features':24,'cells':36,'pairs':12,
      'max_probability_abs_error':max_probability_error,'max_raw_linear_score_abs_error':max_score_error,
      'new_gpu_calls':0,'new_forward_passes':0,'new_fits':0,'semantic_gold':False},indent=2))


if __name__=='__main__': main()
