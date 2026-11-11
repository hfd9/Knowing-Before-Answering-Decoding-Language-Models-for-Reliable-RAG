"""Independently verify structural relations and true-tokenizer identities; no model forward."""
import hashlib
import json
import re
from pathlib import Path
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
MODEL=Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
audit=read(HERE/'cpu-audit.json'); rows=read(HERE/'materials.json')['rows']; refs=read(HERE/'author-review.json')['items']
assert sha(HERE/'materials.json')==audit['materials_sha256'] and sha(HERE/'author-review.json')==audit['author_review_sha256']
assert sha(HERE/'pair-metrics.json')==audit['pair_metrics_sha256'] and sha(MODEL/'tokenizer.json')==audit['tokenizer_sha256']
assert len(rows)==len(refs)==36
template=read(ROOT/'prompts/prompt_robustness_P0_P5.json')['P0']
ref=read(ROOT/'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json')
tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True)
table={}; review={}; quotes=0
for r,a in zip(rows,refs):
    assert r['id']==a['id'] and len(r['docs'])==len(a['evidence'])==5
    assert r['id'].startswith('bind_') and a['status']=='informed_author_draft_not_independent_gold'
    assert r['document_level']==a['state'] and a['target']['entity']!=a['other_entity']
    for i,(doc,e) in enumerate(zip(r['docs'],a['evidence']),1):
        assert e['slot']==i and e['quote']==doc;quotes+=1
    for value in a['possible_values']:
        assert all(value in doc for doc in r['docs'][:2])
    assert f"{a['target']['entity']} and {a['other_entity']} are distinct entries" in r['docs'][2]
    body=''
    if template['pre_docs']: body+=template['pre_docs'].format(question=r['question'])+'\n\n'
    for i,doc in enumerate(r['docs'],1): body+=template['doc_prefix'].format(i=i,doc=doc)
    body+=template['suffix'].format(question=r['question'])
    text=tokenizer.apply_chat_template([{'role':'system','content':ref['instruction']},{'role':'user','content':body}],tokenize=False,add_generation_prompt=True)
    tokens=tokenizer(text,truncation=False,add_special_tokens=False)['input_ids']
    assert r['identity']=={'prompt_sha256':hashlib.sha256(text.encode()).hexdigest(),'input_tokens':len(tokens),
                           'input_token_ids_sha256':hashlib.sha256(json.dumps(tokens).encode()).hexdigest()}
    a1,a2=(set(re.sub('[^a-z0-9]+',' ',d.lower()).split()) for d in r['docs'][:2])
    assert abs(r['slot12_word_jaccard']-len(a1&a2)/len(a1|a2))<1e-15
    key=(r['original_id'],r['document_level'],r['question_level']); assert key not in table
    table[key]=r; review[key]=a
assert len(table)==36 and quotes==180
counts={'S-C':[],'S-I':[]}; deltas={'S-C':[],'S-I':[]}; equal_sets=0
for base in sorted({r['original_id'] for r in rows}):
    for wording in 'AB':
        s,i,c=(table[(base,k,wording)] for k in 'SIC'); a=review[(base,'S',wording)]; v1,v2=a['possible_values']
        assert s['question']==i['question']==c['question'] and s['docs'][2:]==i['docs'][2:]==c['docs'][2:]
        assert s['docs'][1].replace(v1,v2,1)==c['docs'][1] and s['docs'][0]==c['docs'][0]
        assert all(s['docs'][j].replace(a['target']['entity'],a['other_entity'],1)==i['docs'][j] for j in range(2))
        words=lambda text:set(re.sub('[^a-z0-9]+',' ',text.lower()).split())
        equal_sets+=all(words(s['docs'][j])==words(c['docs'][j]) for j in range(2))
        assert review[(base,'I',wording)]['assigned_target_values']==[]
        for name,r in [('S-C',c),('S-I',i)]:
            counts[name].append(r['identity']['input_tokens']-s['identity']['input_tokens'])
            deltas[name].append(r['slot12_word_jaccard']-s['slot12_word_jaccard'])
assert all(len(v)==12 and all(x==0 for x in v) for v in counts.values())
assert all(x==0 for x in deltas['S-C']) and all(0<x<0.003 for x in deltas['S-I'])
assert equal_sets==12
assert len(read(HERE/'pair-metrics.json')['pairs'])==24
print(json.dumps({'status':'passed_cpu_independent_render_and_counts','inputs':36,'citations':quotes,
 'prompt_and_token_ids_checked':36,'S_C_equal_token':12,'S_I_equal_token':12,
 'S_C_equal_jaccard':12,'S_C_equal_word_sets_both_slots':equal_sets,
 'S_I_max_jaccard_difference':max(deltas['S-I']),
 'model_forward':False,'gpu_accessed':False,
 'limitation':'Literal substitution and token identity do not prove semantic sufficiency or independent gold.'}))
