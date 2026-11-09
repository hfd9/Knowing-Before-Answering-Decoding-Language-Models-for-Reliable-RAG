"""Independent CPU verification of the completed neutral control and frozen probe."""
import hashlib
import json
from pathlib import Path
import pickle

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/qwen2.5-3b-probe-neutral-length-control-20261109-v1'
ARCH=ROOT/'docs/review/2026-11-09-probe-neutral-length-control-v1'
SOURCE=ROOT/'runs/qwen2.5-3b-probe-support-expression-v1'
PROBE=ROOT/'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl'
REF=ROOT/'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
MODES=('answer','refuse','conflict')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    protocol=read(RUN/'protocol.json'); src_protocol=read(SOURCE/'protocol.json')
    ref=read(REF); report=read(RUN/'report.json'); states=read(RUN/'states.json')
    rows=read(RUN/'materials/inputs.json'); comparisons=read(RUN/'materials/comparisons.json')
    for name in ('protocol.json','materials/inputs.json','materials/comparisons.json'):
        assert (RUN/name).read_bytes()==(ARCH/name).read_bytes(), name
    assert protocol['operator']=='user' and protocol['input_rows']==protocol['new_forwards']==13
    assert protocol['new_answers']==protocol['new_fits']==0 and not protocol['held_out_380_access']
    assert protocol['model']==ref['model']==src_protocol['model']
    assert protocol['model_files_sha256']==ref['model_files_sha256']
    assert all(ref['model_files_sha256'][k]==v for k,v in src_protocol['backbone_signature']['model_files'].items())
    assert src_protocol['frozen_probe_layer']==28 and 'hidden_states[l+1][0,-1,:]' in src_protocol['feature_convention']
    assert sha(PROBE)==protocol['source_probe_sha256']=='db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'
    for name,value in protocol['dependencies'].items():
        assert sha(ROOT/name)==value,name
    assert states['protocol_sha256']==sha(RUN/'protocol.json')
    records=states['records']; old=read(SOURCE/'states.json')['records']
    assert len(records)==len(rows)==13 and len(comparisons)==12
    assert len({r['id'] for r in records})==13 and [r['id'] for r in records]==[r['id'] for r in rows]
    assert len({r['id'] for r in old})==len(old)==50
    old_by={r['id']:r for r in old}
    assert not (RUN/'last_failure.json').exists()
    assert {p.name for p in (RUN/'attempts').iterdir()}=={f'{i:04d}.json' for i in range(13)}
    assert {p.name for p in (RUN/'features').iterdir()}=={f'{i:04d}.npy' for i in range(13)}
    assert report['status']=='technical_prefill_complete_exposed_development_only'
    assert report['new_forwards']==13 and report['new_answers']==report['new_fits']==0 and report['semantic_gold'] is False
    probe=pickle.loads(PROBE.read_bytes())
    assert probe['layer']==28 and list(probe['router'].classes_)==[0,1,2]
    calibrated=probe['router'].calibrated_classifiers_[0]
    coef=calibrated.estimator.coef_; intercept=calibrated.estimator.intercept_
    a=np.array([c.a_ for c in calibrated.calibrators]); b=np.array([c.b_ for c in calibrated.calibrators])
    max_error=0.0
    def calculate(record,root):
        nonlocal max_error
        path=root/record['feature_file']
        assert sha(path)==record['feature_sha256']
        values=np.load(path,allow_pickle=False)
        assert values.shape==(36,2048) and values.dtype==np.float16 and np.isfinite(values).all()
        assert not np.any(np.all(values==0,axis=1))
        x=values[28][None].astype(np.float32)
        x-=probe['scaler'].mean_; x/=probe['scaler'].scale_
        score=(x@coef.T+intercept)[0]
        sigmoid=1/(1+np.exp(a*score+b)); prob=sigmoid/sigmoid.sum()
        assert record['probe_layer_zero_based']==28 and record['probe_pred']==MODES[int(np.argmax(prob))]
        error=max(abs(float(prob[i])-record['probe_probabilities'][k]) for i,k in enumerate(MODES))
        max_error=max(max_error,error)
        assert error<1e-10
        return values,score,prob
    new_values={}
    for i,(row,record) in enumerate(zip(rows,records)):
        assert read(RUN/'attempts'/f'{i:04d}.json')=={'index':i,'id':row['id'],'protocol_sha256':sha(RUN/'protocol.json')}
        assert record['feature_file']==f'features/{i:04d}.npy' and record['origin']=='new_forward'
        assert record['capture_phase']=='decoder_prefill_without_generation'
        expected=protocol['identities'][row['id']]
        assert record['prompt_sha256']==expected['prompt_sha256'] and record['input_tokens']==expected['input_tokens']
        new_values[row['id']]=calculate(record,RUN)
    old_ids={c[k] for c in comparisons for k in ('positive_id','negative_id')}
    assert len(old_ids)==24
    old_values={i:calculate(old_by[i],SOURCE) for i in old_ids}
    bridge=records[0]; assert bridge['id']=='bridge_support06_D1'
    new_bridge=new_values[bridge['id']][0]; old_bridge=old_values['support06_D1'][0]
    left=new_bridge.astype(np.float32); right=old_bridge.astype(np.float32)
    relative=np.linalg.norm(left-right,axis=1)/np.maximum(np.linalg.norm(right,axis=1),1e-12)
    bridge_l2=float(relative.max())
    bridge_p=float(max(abs(new_values[bridge['id']][2]-old_values['support06_D1'][2])))
    assert bridge_l2<=protocol['bridge_tolerances']['max_layer_relative_l2']
    assert bridge_p<=protocol['bridge_tolerances']['max_probability_absolute_error']
    assert len(report['pairs'])==12 and {p['neutral_id'] for p in report['pairs']}=={r['id'] for r in rows[1:]}
    saved_pairs={r['neutral_id']:r for r in report['pairs']}
    for c in comparisons:
        pair=saved_pairs[c['neutral_id']]
        assert all(pair[k]==c[k] for k in ('base','wording','positive_id','negative_id','neutral_id'))
        assert pair['negative_tokens']==pair['neutral_tokens']==c['negative_identity']['input_tokens']==c['neutral_identity']['input_tokens']
        for label,values in [('positive',old_values[c['positive_id']]),('negative',old_values[c['negative_id']]),('neutral',new_values[c['neutral_id']])]:
            assert pair[label+'_pred']==MODES[int(np.argmax(values[2]))]
            assert all(abs(pair[label+'_probabilities'][k]-float(values[2][i]))<1e-10 for i,k in enumerate(MODES))
        assert abs(pair['negative_minus_neutral_conflict']-(old_values[c['negative_id']][2][2]-new_values[c['neutral_id']][2][2]))<1e-10
    print(json.dumps({'status':'independent_manual_readout_and_bridge_verified',
      'records':13,'attempts':13,'new_features':13,'old_features':24,'pairs':12,
      'full_prompt_token_matched':12,'probe_sha256':sha(PROBE),'layer_zero_based':28,
      'max_manual_probe_probability_abs_error':max_error,'bridge_max_layer_relative_l2':bridge_l2,
      'bridge_max_probability_abs_error':bridge_p,'bridge_max_layer_relative_l2_limit':0.02,
      'bridge_max_probability_abs_error_limit':0.01,'dependencies_verified':len(protocol['dependencies']),
      'semantic_truth_verified':False,'model_output_origin_independently_verified':False,
      'new_gpu_calls':0,'new_forward_passes':0,'new_fits':0},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
