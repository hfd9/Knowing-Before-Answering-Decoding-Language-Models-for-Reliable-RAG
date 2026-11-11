"""Independent CPU review of draft identities, references and pair metrics."""
import hashlib
import json
import re
from pathlib import Path
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[3]; HERE=Path(__file__).resolve().parent
MODEL=Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(HERE/'cpu-audit.json'); rows=read(HERE/'materials.json')['rows']; refs=read(HERE/'author-review.json')['items']
assert sha(HERE/'materials.json')==plan['materials_sha256'] and sha(HERE/'author-review.json')==plan['author_review_sha256']
assert sha(HERE/'pair-metrics.json')==plan['pair_metrics_sha256'] and sha(MODEL/'tokenizer.json')==plan['tokenizer_sha256']
assert len(rows)==len(refs)==36
template=read(ROOT/'prompts/prompt_robustness_P0_P5.json')['P0']
reference=read(ROOT/'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json')
tok=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True)
table={}; quote_count=0
for r,ref in zip(rows,refs):
    assert r['id']==ref['id'] and len(r['docs'])==len(ref['evidence'])==5
    assert r['id'].startswith('rep_') and ref['status']=='informed_author_draft_not_independent_gold'
    for n,(doc,e) in enumerate(zip(r['docs'],ref['evidence']),1):
        assert e['slot']==n and e['quote']==doc;quote_count+=1
    if r['document_level']=='I':
        for candidate in ref['hypothetical_distinct_values_not_in_input']:
            assert not any(candidate.lower() in d.lower() for d in r['docs'])
    body=''
    if template['pre_docs']: body+=template['pre_docs'].format(question=r['question'])+'\n\n'
    for i,doc in enumerate(r['docs'],1): body+=template['doc_prefix'].format(i=i,doc=doc)
    body+=template['suffix'].format(question=r['question'])
    prompt=tok.apply_chat_template([{'role':'system','content':reference['instruction']},{'role':'user','content':body}],tokenize=False,add_generation_prompt=True)
    tokens=tok(prompt,truncation=False,add_special_tokens=False)['input_ids']
    assert r['identity']=={'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                           'input_tokens':len(tokens),'input_token_ids_sha256':hashlib.sha256(json.dumps(tokens).encode()).hexdigest()}
    a,b=(set(re.sub('[^a-z0-9]+',' ',x.lower()).split()) for x in r['docs'][:2])
    assert abs(r['slot12_word_jaccard']-len(a&b)/len(a|b))<1e-15
    table[(r['original_id'],r['document_level'],r['question_level'])]=r
assert len(table)==36
metrics=read(HERE/'pair-metrics.json'); counts={'S-C':[],'S-I':[]}; overlap_gap=[]
for base in sorted({r['original_id'] for r in rows}):
    for w in 'AB':
        s,i,c=(table[(base,k,w)] for k in 'SIC')
        for label,r,slots in [('S-C',c,[2]),('S-I',i,[1,2])]:
            assert r['question']==s['question']
            assert [j+1 for j,(a,b) in enumerate(zip(s['docs'],r['docs'])) if a!=b]==slots
            counts[label].append(r['identity']['input_tokens']-s['identity']['input_tokens'])
        overlap_gap.append(c['slot12_word_jaccard']-s['slot12_word_jaccard'])
assert len(metrics['pairs'])==24
assert (sum(x==0 for x in counts['S-C']),min(counts['S-C']),max(counts['S-C']))==(10,0,1)
assert (sum(x==0 for x in counts['S-I']),min(counts['S-I']),max(counts['S-I']))==(0,-11,-1)
assert sum(x<0 for x in overlap_gap)==12
print(json.dumps({'status':'passed_cpu_independent_render_and_counts','inputs':36,'citations':quote_count,
 'prompt_and_token_ids_checked':36,'S_C_equal_token':10,'S_I_equal_token':0,
 'S_C_jaccard_lower_in_conflict':12,'model_forward':False,'gpu_accessed':False,
 'limitation':'checks literal identities, not semantics, independence or proof of a sufficient control'},ensure_ascii=False))
