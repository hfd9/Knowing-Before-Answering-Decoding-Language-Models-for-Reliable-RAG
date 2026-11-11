"""Read-only reconstruction of archived feature predictions and pair counts."""
import collections
import hashlib
import json
from pathlib import Path
import statistics

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ART = Path(__file__).resolve().parent
LIVE = ROOT / 'runs/qwen2.5-3b-new-controlled-probe-20261111-v1'
SRC = ART / 'source'
def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

files = sorted(p for p in SRC.rglob('*') if p.is_file())
assert len(files) == 78
assert all(sha(p) == sha(LIVE / p.relative_to(SRC)) for p in files)
states = read(SRC / 'states.json')
records = states['records']
rows = read(SRC / 'materials/inputs.json')
protocol = read(SRC / 'protocol.json')
assert len(records) == len(rows) == 37 and states['protocol_sha256'] == sha(SRC / 'protocol.json')
assert not (LIVE / 'last_failure.json').exists() and not (LIVE / 'states.json.tmp').exists()
probe = joblib.load(ROOT / 'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl')
classes = ['answer', 'refuse', 'conflict']
max_prob_error = 0.0
for i, (r, row) in enumerate(zip(records, rows)):
    assert r['id'] == row['id']
    assert read(SRC / f'attempts/{i:04d}.json') == {'index': i, 'id': r['id'], 'protocol_sha256': states['protocol_sha256']}
    path = SRC / r['feature_file']
    assert sha(path) == r['feature_sha256']
    x = np.load(path, allow_pickle=False)
    assert x.shape == (36, 2048) and np.isfinite(x).all()
    probs = probe['router'].predict_proba(probe['scaler'].transform(x[28][None].astype(np.float32)))[0]
    for c, v in zip(probe['router'].classes_, probs):
        max_prob_error = max(max_prob_error, abs(float(v) - r['probe_probabilities'][classes[int(c)]]))
    assert classes[int(probe['router'].classes_[np.argmax(probs)])] == r['probe_pred']
assert max_prob_error < 1e-9
bridge = rows[0]['source']
oldfile = ROOT / bridge['base'] / bridge['record']['feature_file']
assert sha(oldfile) == bridge['record']['feature_sha256']
old = np.load(oldfile, allow_pickle=False).astype(np.float32)
new = np.load(SRC / records[0]['feature_file'], allow_pickle=False).astype(np.float32)
relative = np.linalg.norm(new-old, axis=1) / np.maximum(np.linalg.norm(old, axis=1), 1e-12)
bridge_error = float(np.max(relative))
oldp = probe['router'].predict_proba(probe['scaler'].transform(old[28][None]))[0]
newp = probe['router'].predict_proba(probe['scaler'].transform(new[28][None]))[0]
bridge_prob_error = float(np.max(np.abs(oldp-newp)))
assert bridge_error <= protocol['bridge_tolerances']['max_layer_relative_l2']
assert bridge_prob_error <= protocol['bridge_tolerances']['max_probability_absolute_error']
table = {(r['original_id'],r['document_level'],r['question_level']):r for r in records[1:]}
assert len(table)==36
reference = {'S':'answer','I':'refuse','C':'conflict'}
counts = {s: dict(collections.Counter(table[b,s,w]['probe_pred'] for b in sorted({x[0] for x in table}) for w in 'AB')) for s in 'SIC'}
ab = {}; changes = {}
for s in 'SIC':
    pairs = [(table[b,s,'A'],table[b,s,'B']) for b in sorted({x[0] for x in table})]
    ab[s] = {'same':sum(a['probe_pred']==b['probe_pred'] for a,b in pairs),
             'same_both_mismatch':sum(a['probe_pred']==b['probe_pred']!=reference[s] for a,b in pairs)}
for s in 'IC':
    pairs = [(table[b,'S',w],table[b,s,w]) for b in sorted({x[0] for x in table}) for w in 'AB']
    changes[s] = {c:{'mean':statistics.mean(b['probe_probabilities'][c]-a['probe_probabilities'][c] for a,b in pairs),
                    'positive':sum(b['probe_probabilities'][c]>a['probe_probabilities'][c] for a,b in pairs)} for c in classes}
print(json.dumps({'archived_files':len(files),'records':len(records),'attempts':37,'feature_arrays':37,
 'max_prediction_probability_error':max_prob_error,'bridge_max_layer_relative_l2':bridge_error,
 'bridge_max_probability_error':bridge_prob_error,'counts':counts,'ab':ab,'changes':changes,
 'first_completed_utc':records[0]['completed_at'],'last_completed_utc':records[-1]['completed_at'],
 'sources':{str(p.relative_to(SRC)):sha(p) for p in files}},ensure_ascii=False,indent=2))
