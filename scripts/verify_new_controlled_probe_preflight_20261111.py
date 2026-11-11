"""Independent CPU preflight over frozen plan, inputs and P0 tokenization; no model forward."""
import hashlib
import json
from pathlib import Path
from transformers import AutoTokenizer

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/qwen2.5-3b-new-controlled-probe-20261111-v1'
SRC=ROOT/'runs/qwen2.5-3b-probe-support-expression-v1'
MODEL=Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def main():
    p=load(RUN/'protocol.json'); rows=load(RUN/'materials/inputs.json')
    materials=load(ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1/materials.json')['rows']
    assert len(rows)==37 and rows[1:]==materials and len({x['id'] for x in rows})==37
    assert p['new_inputs']==36 and p['new_forwards']==37 and p['new_answers']==p['new_fits']==0
    assert p['held_out_380_access'] is False and not (RUN/'states.json').exists()
    assert not (RUN/'last_failure.json').exists()
    assert not (RUN/'attempts').exists() and not (RUN/'features').exists()
    for name,digest in p['dependencies'].items(): assert sha(ROOT/name)==digest,name
    old=load(SRC/'materials/inputs.json'); matches=[x for x in old if x['id']=='support06_D1']; assert len(matches)==1
    for k in ('question','docs','original_id','question_level','document_level'): assert rows[0][k]==matches[0][k]
    ref=load(ROOT/'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json')
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True)
    template=load(ROOT/'prompts/prompt_robustness_P0_P5.json')['P0']
    lengths=[]
    for r in rows:
        body=''
        if template['pre_docs']: body+=template['pre_docs'].format(question=r['question'])+'\n\n'
        for i,doc in enumerate(r['docs'],1): body+=template['doc_prefix'].format(i=i,doc=doc)
        body+=template['suffix'].format(question=r['question'])
        prompt=tokenizer.apply_chat_template([{'role':'system','content':ref['instruction']},{'role':'user','content':body}],tokenize=False,add_generation_prompt=True)
        tokens=tokenizer(prompt,truncation=False,add_special_tokens=False)['input_ids']
        actual={'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'input_tokens':len(tokens),
                'input_token_ids_sha256':hashlib.sha256(json.dumps(tokens).encode()).hexdigest()}
        assert p['identities'][r['id']]==actual,r['id']
        lengths.append(len(tokens))
    print(json.dumps({'status':'passed_cpu_preflight_prepared_not_started','inputs':36,'bridge':1,
        'prompt_token_identities_checked':len(lengths),'total_tokens':sum(lengths),'max_tokens':max(lengths),
        'dependencies':len(p['dependencies']),'model_weights_rehashed':False,'gpu_accessed':False,
        'protocol_sha256':sha(RUN/'protocol.json')},sort_keys=True))
if __name__=='__main__': main()
