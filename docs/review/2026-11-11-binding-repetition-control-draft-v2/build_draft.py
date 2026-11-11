"""Construct a post-result, informed target-binding control draft; CPU only."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parent
SPEC=ROOT/'prompts/new_controlled_probe_20261111_v1.json'
ORIGINAL=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1/materials.json'
MODEL=Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
sys.path.insert(0,str(ROOT/'scripts'))
import probe_neutral_length_control_20261109 as neutral
from transformers import AutoTokenizer

OTHER={'novel01':'instrument Rovan','novel02':'device Vernel','novel03':'ferry Lomir',
       'novel04':'vessel design Meral','novel05':'Kedren rehearsal','novel06':'archive box Vuren'}
ALT={'novel04':'gloss ivory'}
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(x): return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def check_write(p,b,verify):
    if p.exists():
        if p.read_bytes()!=b: raise ValueError('refuse to overwrite different artifact: '+str(p))
    elif verify: raise ValueError('missing artifact: '+str(p))
    else: p.write_bytes(b)
def jac(docs):
    a,b=(set(re.findall(r'[a-z0-9]+',v.lower())) for v in docs[:2])
    return len(a&b)/len(a|b)

def main():
    verify=sys.argv[1:]==['--verify']
    if sys.argv[1:] not in ([],['--verify']): raise ValueError('use --verify or no arguments')
    scenarios=read(SPEC)['scenarios']; old={x['id']:x for x in read(ORIGINAL)['rows']}
    assert len(scenarios)==6 and len(old)==36
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True)
    rows=[]; refs=[]
    for s in scenarios:
        base=s['id']; other=OTHER[base]; alt=ALT.get(base,s['alternate']); value=s['value']
        background=list(s['background'])
        background[0]+=(f" For this register, {s['entity']} and {other} are distinct entries. "
                        "The two listed options are distinct values.")
        def text(lead,subject,v):
            return (f"{lead} {s['condition']}, the {s['field']} for {subject} is {v}. "
                    f"The record also mentions {s['entity']}. Possible {s['field']} values include {value} and {alt}.")
        for state in 'SIC':
            for idx,w in enumerate('AB'):
                subject=other if state=='I' else s['entity']; second=alt if state=='C' else value
                leads=['For','Regarding']; docs=[text(leads[idx],subject,value),text(leads[1-idx],subject,second)]+background
                original=old[f'{base}_{state}_{w}']; assert original['question']==s['question']
                row={'id':f'bind_{base}_{state}_{w}','original_id':base,'question_level':w,
                     'document_level':state,'question':s['question'],'docs':docs,'source_original_id':original['id'],
                     'slot12_word_jaccard':jac(docs)}
                row['identity']=neutral.identity(row,tokenizer); rows.append(row)
                reason={'S':'Both assignments bind the target to the same value; slot 3 defines the distinct entries.',
                        'I':'Both assignments bind the other entry; the target is mentioned but its value is not assigned. The two listed values are possibilities, not target assignments.',
                        'C':'The two assignments bind the target under the same condition to different listed values; slot 3 gives a single-value rule and no priority.'}[state]
                refs.append({'id':row['id'],'state':state,'target':{'entity':s['entity'],'field':s['field'],'condition':s['condition']},
                             'other_entity':other,'possible_values':[value,alt],
                             'assigned_target_values':{'S':[value],'I':[],'C':[value,alt]}[state],
                             'author_reason':reason,'evidence':[{'slot':i+1,'quote':q} for i,q in enumerate(docs)],
                             'status':'informed_author_draft_not_independent_gold',
                             'limits':'Possible value mentions are not assignments to the target; literal checks do not prove absence of indirect inference.'})
    assert len(rows)==len(refs)==36
    table={(r['original_id'],r['document_level'],r['question_level']):r for r in rows}; pairs=[]
    for s in scenarios:
        for w in 'AB':
            a,b,c=(table[(s['id'],k,w)] for k in 'SIC')
            for typ,left,right,expect in [('S-C',a,c,[2]),('S-I',a,b,[1,2])]:
                changes=[j+1 for j,(u,v) in enumerate(zip(left['docs'],right['docs'])) if u!=v]
                assert changes==expect
                pairs.append({'base':s['id'],'wording':w,'comparison':typ,'left_id':left['id'],'right_id':right['id'],
                              'changed_slots':changes,'token_delta':right['identity']['input_tokens']-left['identity']['input_tokens'],
                              'jaccard_delta':right['slot12_word_jaccard']-left['slot12_word_jaccard']})
    assert len(pairs)==24
    summary={}
    for typ in ('S-C','S-I'):
        x=[p for p in pairs if p['comparison']==typ]
        summary[typ]={'pairs':len(x),'equal_token':sum(p['token_delta']==0 for p in x),
                      'identical_jaccard':sum(p['jaccard_delta']==0 for p in x),
                      'max_abs_jaccard_delta':max(abs(p['jaccard_delta']) for p in x)}
    materials={'status':'post_result_informed_cpu_draft_no_collection','rows':rows}
    review={'status':'informed_author_draft_not_independent_gold','author_has_seen_previous_probe_results':True,
            'formal_labels':None,'items':refs}
    mb,rb,pb=map(encoded,(materials,review,{'pairs':pairs,'summary':summary}))
    for name,data in [('materials.json',mb),('author-review.json',rb),('pair-metrics.json',pb)]:check_write(OUT/name,data,verify)
    audit={'status':'cpu_draft_only_no_gpu_release','existing_exposed_bases':6,'new_inputs':36,'new_forwards':0,'new_fits':0,
           'independent_approvals':0,'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (SPEC,ORIGINAL)},
           'tokenizer_sha256':sha(MODEL/'tokenizer.json'),'materials_sha256':hashlib.sha256(mb).hexdigest(),
           'author_review_sha256':hashlib.sha256(rb).hexdigest(),'pair_metrics_sha256':hashlib.sha256(pb).hexdigest(),
           'selected_other_entities':OTHER,'alternate_value_overrides':ALT,
           'selection_disclosure':'After seeing previous results, candidate names for novel03 and novel05 and candidate alternate values for novel04 were tested against tokenizer lengths; no new model or probe outputs were observed.',
           'comparisons':summary}
    check_write(OUT/'cpu-audit.json',encoded(audit),verify)
    print(json.dumps(audit,ensure_ascii=False))
if __name__=='__main__':main()
