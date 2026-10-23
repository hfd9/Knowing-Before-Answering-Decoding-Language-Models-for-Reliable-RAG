"""Independent read-only preparation check: no collector import, model or probe."""
import ast
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/qwen2.5-3b-relation-attachment-v1'
PREFIX='docs/records/2026-10-23-relation-attachment-preparation'


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):
            h.update(block)
    return h.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def check(ok,message):
    if not ok:
        raise ValueError(message)


def main():
    preserved=read(ROOT/(PREFIX+'-preserved.json'))
    for path,expected in preserved.items():
        check(digest(ROOT/path)==expected,'Old source differs: '+path)
    frozen_run=read(ROOT/(PREFIX+'-run-hashes.json'))
    actual={str(p.relative_to(ROOT)):digest(p) for p in RUN.rglob('*') if p.is_file() and p.name!='.run.lock'}
    check(actual==frozen_run,'Preparation run file set/bytes changed')
    rows=read(RUN/'materials/inputs.json')
    local_rows=read(ROOT/(PREFIX+'-inputs.json'))
    check(rows==local_rows and len(rows)==48,'Material copy differs')
    by_id={r['id']:r for r in rows}
    spec=read(ROOT/'prompts/behavior_relation_attachment_materials_v1.json')
    draft=read(ROOT/'prompts/behavior_relation_attachment_design_v1.json')
    author=read(ROOT/'prompts/behavior_relation_attachment_author_review_v1.json')
    check(len(by_id)==48 and set(by_id)==set(author['reviewed_ids']) and author['history_exposed']
          and not author['independent_gold'],'Author input coverage/identity differs')
    expected_ids={f'{s["id"]}_{c}_{v}' for s,c,v in itertools.product(spec['scenarios'],['TQ','OQ','TA','OA'],['v1','v2'])}
    check(set(by_id)==expected_ids,'Incomplete grid')
    check(Counter(r['condition'] for r in rows)=={'TQ':12,'OQ':12,'TA':12,'OA':12},'Cell denominator differs')
    for old in read(ROOT/'docs/records/2026-10-23-behavior-structure-audit-samples.json')['items']:
        check(by_id[old['id']]['question']==old['question'] and by_id[old['id']]['docs']==old['documents'],
              'Earlier example changed')
    worlds=read(RUN/'coordinator/witnesses.json')
    check(worlds==read(ROOT/(PREFIX+'-witnesses.json')) and len(worlds)==36,'World copy/count differs')
    facts={}
    complete_worlds=0
    for row in rows:
        s=next(x for x in spec['scenarios'] if x['id']==row['original_id'])
        check(len(row['docs'])==5,'Wrong slot count')
        query=row['question'].split('what ',1)[1].split(' is assigned to Unit ',1)[0]
        check(query==s['queried_attribute'] and row['question']==draft['question_template'].format(**s),'Question drift')
        assignments=[]
        for i,doc in enumerate(row['docs'],1):
            match=re.fullmatch(r'The (.+?) assigned to Unit (U-[0-9]{3}) is (K-[0-9]{5})\. Unit (U-[0-9]{3}) has a ledger entry\.',doc)
            if match:
                attr,owner,value,nonowner=match.groups()
                assignments.append((i,attr,owner,value,nonowner))
        check(len(assignments)==1,'Expected one code assignment')
        idx,attr,owner,value,nonowner=assignments[0]
        check(idx==s['candidate_slot'] and {owner,nonowner}=={s['target'],s['other']},'Fact arguments differ')
        check(value==s[row['variant']]==row['displayed_candidate'],'Candidate variant differs')
        cell=row['condition']
        check((owner==s['target'])==(cell[0]=='T') and (attr==query)==(cell[1]=='Q'),'Cell/semantic relation mismatch')
        check([d for i,d in enumerate(row['docs'],1) if i!=idx]==[
            d.format(**s) for d in draft['background_templates_in_order']],'Other slots differ')
        check(re.findall(r'K-\d{5}',row['question']+'\n'+'\n'.join(row['docs']))==[value],'Non-displayed value leaked')
        facts[row['id']]=(owner,attr,value)
        if cell!='TQ':
            w=worlds[row['id']]
            packet=dict(question=row['question'],docs=row['docs'])
            encoded=(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
            check(w['input_sha256']==text_sha(encoded) and len(w['worlds'])==2,'Witness input binding differs')
            parsed=[]
            domain=set(itertools.product((s['target'],s['other']),('access code','inspection code')))
            for complete in w['worlds']:
                a={(x['entity'],x['attribute']):x['value'] for x in complete}
                check(len(complete)==len(a)==4 and set(a)==domain and a[(owner,attr)]==value,
                      'World violates known relation')
                parsed.append(a);complete_worlds+=1
            a,b=parsed
            check({k for k in a if a[k]!=b[k]}=={(s['target'],query)},'Worlds change more than target query')
            check({a[(s['target'],query)],b[(s['target'],query)]}=={value,s['witness_alternative']},'Wrong target choices')
        else:
            check(row['id'] not in worlds,'Sufficient cell with I witness')
    protocol=read(RUN/'protocol.json')
    for path,expected in {**protocol['implementation_sha256'],**protocol['source_sha256']}.items():
        check(digest(ROOT/path)==expected,'Frozen execution source differs: '+path)
    check(protocol['new_probe_fits']==0 and protocol['original_fit_budget_remaining']==0
          and not protocol['independent_semantic_approval'] and protocol['collection_allowed'], 'Execution identity differs')
    # Rebuild the exact legacy instruction and P0 prompt without importing the collector/renderer.
    tree=ast.parse((ROOT/'scripts/evidence_experiment.py').read_text())
    instruction=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='FREE_INSTRUCTION' for t in n.targets))
    check(instruction==protocol['instruction'],'Free-answer instruction differs')
    template=read(ROOT/'prompts/prompt_robustness_P0_P5.json')['P0']
    check(template['pre_docs']=='','Unexpected P0 prefix')
    model=Path(protocol['model'])
    metadata_checked=0
    for name,expected in protocol['model_files_sha256'].items():
        if not name.endswith('.safetensors'):
            check(digest(model/name)==expected,'Model/tokenizer metadata differs: '+name)
            metadata_checked+=1
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(str(model),local_files_only=True)
    lengths=[]; token_ids={}
    preflight=read(RUN/'preflight.json')
    prepared={r['id']:r for r in preflight['prompts']}
    check(set(prepared)==set(by_id),'Preflight IDs differ')
    for row in rows:
        body=''.join(template['doc_prefix'].format(i=i,doc=d) for i,d in enumerate(row['docs'],1))
        body+=template['suffix'].format(question=row['question'])
        prompt=tokenizer.apply_chat_template([{'role':'system','content':instruction},{'role':'user','content':body}],
            tokenize=False,add_generation_prompt=True)
        ids=tokenizer(prompt,truncation=False,add_special_tokens=False)['input_ids']
        record=prepared[row['id']]
        check(record['prompt_sha256']==text_sha(prompt) and record['input_tokens']==len(ids)
              and record['input_token_ids_sha256']==text_sha(json.dumps(ids)), 'Prompt/token mismatch')
        check(len(ids)+128<=protocol['context_tokens'],'Context overflow')
        check(re.findall(r'K-\d{5}',prompt)==[row['displayed_candidate']] and row['id'] not in prompt,'Rendered coordination leak')
        token_ids[row['id']]=ids;lengths.append(len(ids))
    check((min(lengths),max(lengths),sum(lengths))==(preflight['input_tokens_min'],preflight['input_tokens_max'],preflight['total_input_tokens']),
          'Token aggregate differs')
    pairs=read(RUN/'coordinator/pairs.json')
    check(len(pairs)==72 and len({(p['left'],p['right']) for p in pairs})==72,'Pair count/uniqueness differs')
    primary_bag_equal=0
    for p in pairs:
        a,b=by_id[p['left']],by_id[p['right']]
        changed=[i+1 for i,(x,y) in enumerate(zip(a['docs'],b['docs'])) if x!=y]
        check(changed==[p['changed_slot']] and a['question']==b['question'],'Pair has uncontrolled edit')
        if p['kind']=='primary_TA_minus_OA':
            check(a['condition']=='TA' and b['condition']=='OA' and a['variant']==b['variant']
                  and a['original_id']==b['original_id'],'Primary pairing differs')
            check(facts[a['id']][1:]==facts[b['id']][1:],'Primary changes attribute/value')
            check(Counter(re.findall(r'\w+',' '.join(a['docs'])))==Counter(re.findall(r'\w+',' '.join(b['docs']))),'Primary lexical bag differs')
            primary_bag_equal+=Counter(token_ids[a['id']])==Counter(token_ids[b['id']])
    primary=[p for p in pairs if p['kind']=='primary_TA_minus_OA']
    check(len(primary)==12,'Primary denominator differs')
    prefix=spec['smoke_prefix_ids']
    expected_order=prefix+sorted(set(by_id)-set(prefix),key=lambda k:text_sha('relation-attachment-order-v1|'+k))
    check(protocol['ordered_ids']==expected_order,'Generation order differs')
    packet=read(RUN/'input_review/packet.json')
    mapping=read(RUN/'coordinator/input_mapping.json')
    anonymous={i['item_id']:i for i in packet['items']}
    check(len(anonymous)==48 and set(mapping)==set(by_id),'Input review mapping differs')
    for row in rows:
        item=anonymous[mapping[row['id']]]
        check(set(item)=={'item_id','question','documents'} and item['question']==row['question']
              and item['documents']==row['docs'],'Anonymous input differs')
    check(not (RUN/'predictions.json').exists() and not (RUN/'generation_attempts').exists(), 'Expected unstarted study')
    result=dict(status='independent_cpu_preparation_verified',independent_semantic_review=False,
        prior_paths_preserved=len(preserved),frozen_run_files=len(frozen_run),inputs=48,scenarios=6,
        sufficient=12,insufficient=36,compatible_worlds=complete_worlds,pairs=72,primary_pairs=len(primary),
        primary_pairs_with_equal_token_multisets=primary_bag_equal,
        input_tokens_min=min(lengths),input_tokens_max=max(lengths),total_input_tokens=sum(lengths),
        exact_prompts_rebuilt=48,implementation_files=len(protocol['implementation_sha256']),
        source_files=len(protocol['source_sha256']),model_metadata_checked=metadata_checked,
        full_weights_checked_by='Collector prepare and verify, not repeated in this independent metadata/token check',
        generated_answers=0,new_fits=0,new_gpu_calls=0,
        implementation_sha256=digest(Path(__file__)),protocol_sha256=digest(RUN/'protocol.json'))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
