"""Join the sealed CLI review to existing generation inputs and frozen probe outputs."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

from transformers import AutoTokenizer
import evidence_experiment as e

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-09-cli-probe-comparison-v1'
FILES={
 'cases':'docs/review/2026-10-23-semantic-claims-v1/coordinator/cases.json',
 'pairs':'docs/review/2026-10-23-semantic-claims-v1/coordinator/pairs.json',
 'packet':'docs/review/2026-10-23-semantic-claims-v1/public/input_packet.json',
 'outputs':'docs/review/2026-10-23-semantic-claims-v1/public/output_packet.json',
 'manifest':'docs/review/2026-10-23-semantic-claims-v1/manifest.json',
 'author':'docs/review/2026-10-23-semantic-claims-author-v1/input-manual.json',
 'cli':'docs/review/2026-11-06-isolated-cli-review-v1/phase1/input_review.json',
 'cli_output':'docs/review/2026-11-06-isolated-cli-review-v1/phase2/claim_review.json',
 'seal':'docs/review/2026-11-06-isolated-cli-review-v1/phase1/input_seal.json',
 'delivery':'docs/review/2026-11-06-isolated-cli-review-v1/coordinator/delivery_stage1.json',
 'delivery2':'docs/review/2026-11-06-isolated-cli-review-v1/coordinator/delivery_stage2.json',
 'corpus':'docs/review/2026-11-09-probe-existing-cache-audit-v1/corpus.csv',
 'preparation':'docs/records/2026-10-21-semantic-transfer-exploratory-preparation-inputs.csv',
 'inputs':'runs/qwen2.5-3b-semantic-transfer-materials-v5/materials/inputs.json',
 'behavior_mapping':'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/coordinator/behavior_mapping.json',
 'predictions':'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/predictions.json',
 'protocol':'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/protocol.json',
 'approved':'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/approved_labels.json',
 'renderer':'scripts/evidence_experiment.py',
 'prompt_renderer':'code/prompts.py',
 'probe':'runs/qwen2.5-3b-free-answer-study/chat/probe/probe.pkl',
}
MODEL='/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct'
PROBE='db6033b84f1fcd30e5e2e31ce4beb262a76920cc06811c57900ad14b8d40858d'


def read(k): return json.loads((ROOT/FILES[k]).read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def textsha(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def rows(k):
    with (ROOT/FILES[k]).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def index(rows,key):
    x={r[key]:r for r in rows}
    if len(x)!=len(rows):raise ValueError('duplicate '+key)
    return x
def csv_bytes(rows):
    f=io.StringIO(newline=''); w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    return f.getvalue().encode('utf-8')


def build():
    cases=index(read('cases')['cases'],'item_id'); packet=index(read('packet')['items'],'item_id')
    answers=index(read('outputs')['items'],'item_id'); cli=index(read('cli')['items'],'item_id')
    cli_output=index(read('cli_output')['items'],'item_id'); original=read('author')
    author={r[0]:dict(zip(original['field_order'],r)) for r in original['rows']}
    assert len(author)==55 and set(cases)==set(packet)==set(answers)==set(cli)==set(cli_output)==set(author) and len(cases)==55
    seal=read('seal'); delivery=read('delivery'); delivery2=read('delivery2')
    assert seal['input_review_sha256']==sha(ROOT/FILES['cli'])
    assert seal['package_manifest_sha256']==sha(ROOT/FILES['manifest'])==delivery['source_manifest_sha256']
    assert sha(ROOT/FILES['packet'])==delivery['stage1_source_hashes']['input_packet.json']
    assert delivery['answers_delivered'] is False and delivery['author_results_delivered'] is False
    assert delivery2['delivered_at']>seal['sealed_at']>delivery['recorded_at']
    assert delivery2['input_sealed_at']==seal['sealed_at'] and delivery2['input_review_sha256']==seal['input_review_sha256']
    assert delivery2['input_seal_sha256']==sha(ROOT/FILES['seal'])
    assert delivery2['stage2_source_hashes']['output_packet.json']==sha(ROOT/FILES['outputs'])
    assert delivery2['author_results_delivered'] is False and delivery2['coordinator_mapping_delivered'] is False
    assert read('cli_output')['sealed_input_review_sha256']==seal['input_review_sha256']
    inputs=index(read('inputs'),'id'); predicted_payload=read('predictions'); predictions=index(predicted_payload['records'],'id')
    preparation=index(rows('preparation'),'id')
    corpus=index([r for r in rows('corpus') if r['dataset']=='transfer240'],'id')
    protocol=read('protocol'); approved=read('approved'); behavior_mapping=read('behavior_mapping')
    assert predicted_payload['protocol_sha256']==sha(ROOT/FILES['protocol'])
    assert len(behavior_mapping)==len(set(behavior_mapping.values()))==240
    assert len(inputs)==len(predictions)==len(preparation)==len(corpus)==len(approved)==240
    assert all(v is None for v in approved.values())
    assert protocol['model']==MODEL and protocol['fixed_layer_zero_based']==28
    assert sha(ROOT/FILES['probe'])==PROBE
    assert [v for k,v in protocol['sources'].items() if k.endswith('/chat/probe/probe.pkl')]==[PROBE]
    for k in ('renderer','prompt_renderer'):
        assert sha(ROOT/FILES[k])==protocol['implementation_sha256'][FILES[k]]
    for name,expected in protocol['model_files'].items(): assert sha(Path(MODEL)/name)==expected
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    linked=[]; excluded=[]; cited=0
    category={'answerable':'answer','insufficient':'refuse','conflict':'conflict','ambiguous':None}
    for item in sorted(cases):
        case=cases[item]; check=cli[item]; old=author[item]; out=cli_output[item]
        assert check['status']=='reviewed' and out['status']=='reviewed'
        if case['source_family']!='old':
            excluded.append({'item_id':item,'source_id':case['source_id'],'source_family':case['source_family'],
                             'reason':'relation-attachment case; no same-input frozen probe linked in this task',
                             'CLI_input':check['answerability'],'author55_input':old['answerability']})
            continue
        sid=case['source_id']; inp=inputs[sid]; rec=predictions[sid]; prior=corpus[sid]; pre=preparation[sid]
        assert behavior_mapping[sid]==case['source_item_id']
        assert sid==rec['id']==prior['id']==pre['id'] and case['original_id']==inp['original_id']==rec['original_id']==prior['original_id']
        assert case['original_condition']==inp['condition']==rec['condition']==prior['condition']
        assert inp['question']==packet[item]['question']==case['question']
        assert inp['docs']==packet[item]['documents'] and len(inp['docs'])==5
        assert answers[item]['answer']==case['full_answer']==rec['raw_output']
        assert textsha(rec['raw_output'])==rec['raw_output_sha256']==prior['output_sha256']
        prompt=e.render_input(inp,'free_answer','chat',tok); tokens=e.encode(tok,prompt,'chat')['input_ids']
        assert textsha(prompt)==rec['prompt_sha256']==prior['prompt_sha256']==pre['prompt_sha256']
        assert len(tokens)==rec['input_tokens']==int(prior['input_tokens'])==int(pre['input_tokens'])
        assert prior['feature_path']=='runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/'+rec['feature_file']
        assert rec['feature_sha256']==prior['feature_sha256']==sha(ROOT/prior['feature_path'])
        assert rec['probe_layer_zero_based']==28 and rec['probe_decision_pre_first_token'] is True
        assert prior['calibrated_pred']==rec['probe_pred'] and all(abs(float(prior['p_'+k])-rec['probe_probabilities'][k])<1e-14 for k in ('answer','refuse','conflict'))
        for ref in check['document_support']:
            doc=inp['docs'][ref['document_index']-1]
            assert doc[ref['start']:ref['end']]==ref['quote']; cited+=1
        assert item==check['item_id']==old['item_id']
        assert check['answerability'] in category and old['answerability'] in category
        expected=category[check['answerability']]
        behavior=json.loads(prior['existing_behavior'])
        linked.append({'item_id':item,'source_id':sid,'source_item_id':case['source_item_id'],
          'original_id':inp['original_id'],'partition':inp['partition'],'expression':inp['expression'],
          'condition':inp['condition'],'selection_group':case['selection_group'],
          'author55_input':old['answerability'],'author55_missing_link':old['missing_link'],'author55_ambiguity':old['ambiguity'],
          'CLI_input':check['answerability'],'CLI_target_interpretation':check['target_interpretation'],
          'CLI_missing_link':check['missing_link'],'CLI_ambiguity':check['ambiguity'],
          'CLI_input_document_support':json.dumps(check['document_support'],ensure_ascii=False,sort_keys=True),
          'author55_CLI_disagree':old['answerability']!=check['answerability'],
          'earlier_transfer_author_reference':prior['author_reference'],
          'probe_prediction':rec['probe_pred'],'probe_matches_CLI_descriptive': '' if expected is None else rec['probe_pred']==expected,
          'probe_p_answer':rec['probe_probabilities']['answer'],'probe_p_refuse':rec['probe_probabilities']['refuse'],
          'probe_p_conflict':rec['probe_probabilities']['conflict'],
          'prior_behavior_has_substantive_answer':behavior['has_substantive_answer'],
          'prior_behavior_acknowledges_insufficiency':behavior['acknowledges_insufficiency'],
          'CLI_gives_specific_target_answer':out['gives_specific_target_answer'],
          'CLI_target_claim_supported':out['target_claim_supported'],
          'CLI_explanation_all_claims_supported':out['explanation_all_claims_supported'],
          'input_prompt_sha256':rec['prompt_sha256'],'input_tokens':rec['input_tokens'],
          'output_sha256':rec['raw_output_sha256'],'feature_sha256':rec['feature_sha256']})
    assert len(linked)==52 and len(excluded)==3 and Counter(r['condition'] for r in linked)=={'I':26,'S':26}
    assert len({r['original_id'] for r in linked})==13
    by_source={r['source_id']:r for r in linked}; paired=[]
    for p in read('pairs')['pairs']:
        a=by_source[p['source_S_id']]; b=by_source[p['source_I_id']]
        assert a['original_id']==b['original_id']==p['original_id'] and a['expression']==b['expression']==p['expression']
        paired.append({'original_id':p['original_id'],'expression':p['expression'],
                       'S_item_id':a['item_id'],'I_item_id':b['item_id'],
                       'S_source_id':a['source_id'],'I_source_id':b['source_id'],
                       'S_author55':a['author55_input'],'I_author55':b['author55_input'],
                       'S_CLI':a['CLI_input'],'I_CLI':b['CLI_input'],
                       'S_probe':a['probe_prediction'],'I_probe':b['probe_prediction'],
                       'S_behavior_answer':a['prior_behavior_has_substantive_answer'],
                       'I_behavior_answer':b['prior_behavior_has_substantive_answer']})
    assert len(paired)==26 and len({(p['original_id'],p['expression']) for p in paired})==26
    i_subset=[r for r in linked if r['condition']=='I']
    selected_refuse=[r for r in i_subset if r['probe_prediction']=='refuse']
    paired_distribution=Counter((r['S_probe'],r['I_probe']) for r in paired)
    summary={'status':'selected_existing_cli_review_probe_linkage_descriptive_not_independent_gold',
       'input_review_sealed_at':seal['sealed_at'],'CLI_reviewer':'CLI20261106R01',
       'reviewer_context':'single LLM, self-report and visible trace; complete private context not authenticated',
       'selection':'23 answer anchors plus 3 same-base nonanswers and 26 S controls; outcome-selected, not representative',
       'reviewed_input_total':55,'strictly_linked':52,'excluded_relation_cases':3,'original_bases':13,'S_I_pairs':26,
       'CLI_all_counts':dict(Counter(x['answerability'] for x in cli.values())),
       'author55_all_counts':dict(Counter(x['answerability'] for x in author.values())),
       'selected_counts':dict(Counter(x['selection_group'] for x in linked)),
       'linked_author_CLI_disagreements':sum(x['author55_CLI_disagree'] for x in linked),
       'excluded_author_CLI_disagreements':sum(x['author55_input']!=x['CLI_input'] for x in excluded),
       'linked_CLI_counts':dict(Counter(x['CLI_input'] for x in linked)),
       'linked_probe_counts':dict(Counter(x['probe_prediction'] for x in linked)),
       'selected_I_probe_by_prior_behavior':{pred:dict(Counter(r['prior_behavior_has_substantive_answer'] for r in i_subset if r['probe_prediction']==pred)) for pred in ('answer','refuse','conflict')},
       'selected_I_probe_refuse_rows':[{'item_id':r['item_id'],'source_id':r['source_id'],'original_id':r['original_id'],
                                        'expression':r['expression'],'prior_behavior_has_substantive_answer':r['prior_behavior_has_substantive_answer']} for r in selected_refuse],
       'selected_I_CLI_target_support':dict(Counter(r['CLI_target_claim_supported'] for r in i_subset)),
       'paired_S_I_probe_categories':{s+'|'+i:count for (s,i),count in sorted(paired_distribution.items())},
       'paired_both_match_CLI':sum(r['S_CLI']=='answerable' and r['I_CLI']=='insufficient' and r['S_probe']=='answer' and r['I_probe']=='refuse' for r in paired),
       'linked_author_CLI_disagreement_items':[r['item_id'] for r in linked if r['author55_CLI_disagree']],
       'by_condition':{},'paired_rows':26,'selected_CLI_input_citations_checked':cited,
       'independent_semantic_approval':0,'formal_labels_added':0,'new_model_calls':0,'new_fits':0,'held_out_380_accessed':False,
       'source_sha256':{path:sha(ROOT/path) for path in FILES.values()}}
    for condition in ('S','I'):
        subset=[r for r in linked if r['condition']==condition]
        summary['by_condition'][condition]={'rows':len(subset),'CLI_input':dict(Counter(x['CLI_input'] for x in subset)),
          'author55_input':dict(Counter(x['author55_input'] for x in subset)),
          'earlier_transfer_author_reference':dict(Counter(x['earlier_transfer_author_reference'] for x in subset)),
          'probe':dict(Counter(x['probe_prediction'] for x in subset)),
          'probe_matches_CLI':sum(x['probe_matches_CLI_descriptive'] is True for x in subset),
          'probe_not_matches_CLI':sum(x['probe_matches_CLI_descriptive'] is False for x in subset),
          'probe_CLI_unknown':sum(x['probe_matches_CLI_descriptive']=='' for x in subset),
          'prior_behavior_has_substantive_answer':dict(Counter(x['prior_behavior_has_substantive_answer'] for x in subset)),
          'CLI_gives_specific_target_answer':dict(Counter(str(x['CLI_gives_specific_target_answer']) for x in subset))}
    return {'linked.csv':csv_bytes(linked),'excluded.csv':csv_bytes(excluded),'pairs.csv':csv_bytes(paired),
            'summary.json':(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()}


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--stage',required=True,choices=['analyze','verify']);args=parser.parse_args()
    results=build(); OUT.mkdir(parents=True,exist_ok=True)
    for name,data in results.items():
        path=OUT/name
        if args.stage=='analyze':
            with path.open('xb') as f:f.write(data)
        else: assert path.read_bytes()==data,name
    print(json.dumps({'status':'linked_descriptively_no_new_review','stage':args.stage,'linked':52,'excluded':3,'pairs':26}))


if __name__=='__main__':main()
