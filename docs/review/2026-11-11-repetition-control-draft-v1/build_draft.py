"""Build informed, post-result CPU-only draft from six already exposed scenarios."""
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SPEC=ROOT/'prompts/new_controlled_probe_20261111_v1.json'
ORIGINAL=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1/materials.json'
sys.path.insert(0,str(ROOT/'scripts'))
import probe_neutral_length_control_20261109 as neutral
from transformers import AutoTokenizer

MODEL='/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v): return (json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
def check_write(p,b,verify):
    if p.exists():
        if p.read_bytes()!=b: raise ValueError('existing output differs: '+str(p))
    elif verify: raise ValueError('missing output: '+str(p))
    else: p.write_bytes(b)

def main():
    verify=sys.argv[1:]==['--verify']
    if sys.argv[1:] not in ([],['--verify']): raise ValueError('use --verify or no arguments')
    source=read(SPEC)['scenarios']; old=read(ORIGINAL)['rows']; old_by={r['id']:r for r in old}
    assert len(source)==6 and len(old_by)==36
    tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    rows=[]; refs=[]
    for s in source:
        for state in 'SIC':
            for i,w in enumerate('AB'):
                old_id=f"{s['id']}_{state}_{w}"; original=old_by[old_id]
                first=s['missing'][i] if state=='I' else s['support'][i]
                second={'S':s['support'][1-i], 'I':s['missing'][1-i], 'C':s['conflict'][1-i]}[state]
                docs=[first,second]+s['background']
                assert original['question']==s['question'] and original['docs'][0]==first
                assert original['docs'][2:]==docs[2:]
                r={'id':f"rep_{s['id']}_{state}_{w}",'original_id':s['id'],'question_level':w,'document_level':state,
                   'question':s['question'],'docs':docs,'source_original_id':old_id}
                ident=neutral.identity(r,tokenizer)
                def terms(t): return set(re.findall(r'[a-z0-9]+',t.lower()))
                a,b=map(terms,docs[:2]); overlap=len(a&b)/len(a|b)
                r['identity']=ident; r['slot12_word_jaccard']=overlap; rows.append(r)
                ref={'id':r['id'],'target':{k:s[k] for k in ('entity','field','condition')},
                     'state':state,'proposed_probe_class':{'S':'answer','I':'refuse','C':'conflict'}[state],
                     'values':{'S':[s['value']],'I':[],'C':[s['value'],s['alternate']]}[state],
                     'evidence':[{'slot':j+1,'quote':q} for j,q in enumerate(docs)],
                     'author_reason':s['review'],'status':'informed_author_draft_not_independent_gold',
                     'limits':'all five slots retained for review; lexical identity does not certify semantics'}
                if state=='I': ref['hypothetical_distinct_values_not_in_input']=[s['value'],s['alternate']]
                refs.append(ref)
    assert len(rows)==len(refs)==36
    table={(r['original_id'],r['document_level'],r['question_level']):r for r in rows}
    pairs=[]
    for s in source:
        for w in 'AB':
            a,b,c=(table[(s['id'],k,w)] for k in 'SIC')
            assert a['question']==b['question']==c['question']
            for typ,left,right,expected in [('S-C',a,c,[2]),('S-I',a,b,[1,2])]:
                slots=[j+1 for j,(u,v) in enumerate(zip(left['docs'],right['docs'])) if u!=v]
                assert slots==expected,(typ,slots)
                pairs.append({'base':s['id'],'wording':w,'comparison':typ,'left':left['id'],'right':right['id'],
                    'changed_slots':slots,'token_delta':right['identity']['input_tokens']-left['identity']['input_tokens'],
                    'jaccard_delta':right['slot12_word_jaccard']-left['slot12_word_jaccard']})
    assert len(pairs)==24
    comparisons={}
    for typ in ('S-C','S-I'):
        x=[p for p in pairs if p['comparison']==typ]; t=[p['token_delta'] for p in x]
        comparisons[typ]={'n':len(x),'token_equal':sum(v==0 for v in t),'token_delta_min':min(t),'token_delta_max':max(t)}
    group={}
    for state in 'SIC':
        x=[r['slot12_word_jaccard'] for r in rows if r['document_level']==state]
        group[state]={'n':len(x),'min':min(x),'mean':statistics.mean(x),'max':max(x)}
    materials={'status':'post_result_informed_cpu_draft_no_collection','rows':rows}
    review={'status':'informed_author_draft_not_independent_gold','author_has_seen_original_probe_results':True,
            'formal_labels':None,'items':refs}
    mb=encoded(materials); rb=encoded(review); pb=encoded({'pairs':pairs,'comparisons':comparisons,'overlap':group})
    check_write(OUT/'materials.json',mb,verify); check_write(OUT/'author-review.json',rb,verify)
    check_write(OUT/'pair-metrics.json',pb,verify)
    summary={'status':'cpu_draft_only_no_gpu_release','bases':6,'inputs':36,'slots':180,'pairs':24,
             'existing_bases_exposed':True,'new_model_forwards':0,'new_fits':0,'independent_approvals':0,
             'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (SPEC,ORIGINAL)},
             'materials_sha256':hashlib.sha256(mb).hexdigest(),'author_review_sha256':hashlib.sha256(rb).hexdigest(),
             'pair_metrics_sha256':hashlib.sha256(pb).hexdigest(),
             'tokenizer_sha256':sha(Path(MODEL)/'tokenizer.json'),'comparisons':comparisons,'overlap':group}
    check_write(OUT/'cpu-audit.json',encoded(summary),verify)
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__': main()
