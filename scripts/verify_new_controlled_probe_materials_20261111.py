"""Independent structural, provenance, overlap and tokenizer check; no model forward."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from collections import Counter

from transformers import AutoTokenizer
import evidence_experiment as e

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-11-new-controlled-exploration-v1'
MODEL='/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(s): return tuple(re.findall(r'\w+',unicodedata.normalize('NFKC',s).casefold()))
def load(p): return json.loads(p.read_text(encoding='utf-8'))

def main():
    spec=load(ROOT/'prompts/new_controlled_probe_20261111_v1.json')
    material=load(OUT/'materials.json'); reviews=load(OUT/'author-review.json'); seal=load(OUT/'material-seal.json')
    assert seal['spec_sha256']==sha(ROOT/'prompts/new_controlled_probe_20261111_v1.json')
    assert seal['materials_sha256']==sha(OUT/'materials.json') and seal['review_sha256']==sha(OUT/'author-review.json')
    rows=material['rows']; judged={r['id']:r for r in reviews['items']}
    assert len(rows)==len(judged)==36 and len({r['id'] for r in rows})==36
    assert len({r['id'] for r in spec['scenarios']})==6
    table={(r['original_id'],r['document_level'],r['question_level']):r for r in rows}
    for s in spec['scenarios']:
        for state in ('S','I','C'):
            for i,word in enumerate(('A','B')):
                r=table[(s['id'],state,word)]; j=judged[r['id']]
                assert r['question']==s['question'] and len(r['docs'])==5
                assert r['docs'][2:]==s['background'] and j['state']==state
                assert j['proposed_probe_class']=={'S':'answer','I':'refuse','C':'conflict'}[state]
                assert r['docs'][0]==s['missing' if state=='I' else 'support'][i]
                assert r['docs'][1]==(s['conflict'][i] if state=='C' else s['neutral'])
                assert all(isinstance(x,str) and x.strip() for x in r['docs'])
                for q in j['evidence']: assert q['quote'] in r['docs'][q['slot']-1]
                if state=='I':
                    alltext=' '.join(r['docs']).casefold()
                    assert s['value'].casefold() not in alltext and s['alternate'].casefold() not in alltext
                assert s['value'].casefold() in r['docs'][0].casefold() if state != 'I' else True
                if state=='C': assert s['alternate'].casefold() in r['docs'][1].casefold()
        for word in ('A','B'):
            S,I,C=(table[s['id'],state,word] for state in ('S','I','C'))
            assert [i+1 for i in range(5) if S['docs'][i]!=I['docs'][i]]==[1]
            assert [i+1 for i in range(5) if S['docs'][i]!=C['docs'][i]]==[2]
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    lengths={r['id']:len(e.encode(tok,e.render_input(r,'free_answer','chat',tok),'chat')['input_ids']) for r in rows}
    assert max(lengths.values())<=load(Path(MODEL)/'config.json')['max_position_embeddings']
    manifest=ROOT/'runs/qwen2.5-3b-small/data/manifest.json'
    assert sha(manifest)=='3fc899266cfad2009dc3f9baa42050fe37a822eb448afea6b2b3f347fbee3a24'
    manifest_data=load(manifest); oldq=set(); olddocs=set()
    for split in ('train','val','test'):
        p=ROOT/f'runs/qwen2.5-3b-small/data/instances_{split}.jsonl'
        assert sha(p)==manifest_data['splits'][split]['sha256']
        for line in p.read_text().splitlines():
            row=json.loads(line); oldq.add(norm(row['question'])); olddocs.update(map(norm,row['docs']))
    transfer=ROOT/'runs/qwen2.5-3b-semantic-transfer-materials-v5/materials/inputs.json'
    assert sha(transfer)=='2b0ed2bde91624a7eab2eec38c66f4d2d9c2f875760ca7d49995c847c512ae97'
    for row in load(transfer): oldq.add(norm(row['question'])); olddocs.update(map(norm,row['docs']))
    newq={norm(r['question']) for r in rows}; newdocs={norm(d) for r in rows for d in r['docs']}
    exactq=len(newq&oldq); exactdoc=len(newdocs&olddocs)
    nearq=0
    for q in newq:
        a=set(q)
        if len(a)>=5 and any(len(set(o))>=5 and len(a&set(o))/len(a|set(o))>=.8 for o in oldq): nearq+=1
    short=sum(len(d)<16 for d in newdocs)
    print(json.dumps({'status':'passed_structural_informed_not_semantic_gold','bases':len(spec['scenarios']),
        'inputs':len(rows),'input_slots':sum(len(r['docs']) for r in rows),
        'min_tokens':min(lengths.values()),'max_tokens':max(lengths.values()),'total_tokens':sum(lengths.values()),
        'question_exact_matches':exactq,'question_jaccard_ge_0_8':nearq,'document_exact_matches':exactdoc,
        'new_unique_documents':len(newdocs),'new_unique_documents_under_16_tokens':short,
        'overlap_scope':'old train200 val95 diagnostic100 transfer30 only; no sealed 380, old remainder or pretraining',
        'material_sha256':sha(OUT/'materials.json'),'author_review_sha256':sha(OUT/'author-review.json')},sort_keys=True))
if __name__=='__main__': main()
