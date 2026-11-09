"""Independent CPU material/identity check for the prepared neutral control."""
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer
import evidence_experiment as e

ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'docs/review/2026-11-09-probe-neutral-length-control-v1'
RUN=ROOT/'runs/qwen2.5-3b-probe-neutral-length-control-20261109-v1'
SOURCE=ROOT/'runs/qwen2.5-3b-probe-support-expression-v1'
SPEC=ROOT/'prompts/probe_neutral_length_control_20261109.json'
MODEL='/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ident(row,tok):
    prompt=e.render_input(row,'free_answer','chat',tok)
    ids=tok(prompt,truncation=False,add_special_tokens=False)['input_ids']
    return {'prompt_sha256':sha(prompt.encode()),'input_tokens':len(ids),
            'input_token_ids_sha256':sha(json.dumps(ids).encode())}


def main():
    for name in ('protocol.json','materials/inputs.json','materials/comparisons.json'):
        assert (ARCH/name).read_bytes()==(RUN/name).read_bytes(), name
    protocol=read(ARCH/'protocol.json'); rows=read(ARCH/'materials/inputs.json')
    comparisons=read(ARCH/'materials/comparisons.json'); spec=read(SPEC)
    originals={x['id']:x for x in read(SOURCE/'materials/inputs.json')}
    records={x['id']:x for x in read(SOURCE/'states.json')['records']}
    by={x['id']:x for x in rows}
    assert len(by)==len(rows)==13 and len(comparisons)==12
    assert protocol['new_forwards']==13 and protocol['new_answers']==protocol['new_fits']==0
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    bridge=rows[0]; original=originals[spec['bridge_source_id']]
    assert bridge['question']==original['question'] and bridge['docs']==original['docs']
    assert ident(bridge,tok)==protocol['identities'][bridge['id']]
    assert bridge['source']['record']==records[spec['bridge_source_id']]
    found=[]
    for pair in comparisons:
        positive=originals[pair['positive_id']]; negative=originals[pair['negative_id']]
        neutral=by[pair['neutral_id']]; base,wording=pair['base'],pair['wording']
        assert (base,wording) not in found and base in spec['negative_bases'] and wording in spec['wordings']
        found.append((base,wording))
        assert positive['question']==negative['question']==neutral['question']
        changed=[i for i in range(5) if positive['docs'][i]!=negative['docs'][i]]
        assert [i+1 for i in changed]==pair['changed_document_slots'] and len(changed)==2
        for i in range(5):
            if i in changed:
                assert negative['docs'][i]==positive['docs'][i]+' '+pair['negative_suffix']
                assert neutral['docs'][i]==positive['docs'][i]+' '+spec['suffixes'][base]
            else:
                assert positive['docs'][i]==negative['docs'][i]==neutral['docs'][i]
        for row,label in ((positive,'positive_identity'),(negative,'negative_identity'),(neutral,'neutral_identity')):
            observed=ident(row,tok)
            assert observed==pair[label]
            if row is neutral:
                assert observed==protocol['identities'][row['id']]
            else:
                assert observed['prompt_sha256']==records[row['id']]['prompt_sha256']
                assert observed['input_tokens']==records[row['id']]['input_tokens']
                rec=records[row['id']]
                assert sha((SOURCE/rec['feature_file']).read_bytes())==rec['feature_sha256']
        assert pair['neutral_identity']['input_tokens']==pair['negative_identity']['input_tokens']
    assert set(found)=={(b,w) for b in spec['negative_bases'] for w in spec['wordings']}
    print(json.dumps({'status':'material_and_saved_input_identity_verified','fixed_pairs':12,
                      'changed_target_slots':24,'cached_source_feature_hashes':24,
                      'matched_complete_prompt_lengths':12,'bridge_inputs':1,
                      'semantic_truth_verified':False,'model_loaded':False,'gpu_accessed':False}))


if __name__=='__main__':
    main()
