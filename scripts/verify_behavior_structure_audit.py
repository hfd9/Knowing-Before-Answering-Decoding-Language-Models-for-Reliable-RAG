"""Independent stdlib checks of existing sources, draft examples and world pairs."""
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
P = 'docs/records/2026-10-23-behavior-structure-audit'


def read(name):
    return json.loads((ROOT/name).read_text())


def sha(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def check(ok, message):
    if not ok:
        raise ValueError(message)


def table(name):
    with (ROOT/name).open(newline='') as f:
        return list(csv.DictReader(f))


def main():
    report = read(P+'.json')
    source_hashes = report['source_sha256']
    preserved = read(P+'-preserved.json')
    for path, digest in {**source_hashes, **preserved}.items():
        check(sha(path) == digest, 'Source bytes differ: '+path)
    old_rows = table('docs/records/2026-10-21-semantic-transfer-exploratory-behavior-cells.csv')
    irows = [r for r in old_rows if r['exposed_author_input_mode']=='refuse']
    selected = [r for r in irows if r['has_substantive_answer']=='yes']
    check(len(irows)==60 and len(selected)==23
          and Counter(r['has_substantive_answer'] for r in irows)=={'yes':23,'no':37}, 'Old counts differ')
    audit_rows = table(P+'-cases.csv')
    old_audit = read('docs/records/2026-10-21-insufficient-answer-audit.json')['cases']
    check(len(audit_rows)==23 and {r['id'] for r in audit_rows}=={r['id'] for r in selected}, '23-row join differs')
    for r in audit_rows:
        c = old_audit[int(r['audit_json_pointer'].rsplit('/',1)[1])]
        check(c['id']==r['id'] and c['output']==r['old_output'] and c['question']==r['question']
              and c['primary_pattern']==r['old_pattern'] and c['boundary']==r['old_boundary'], 'Old coding changed')
    bmat = read('runs/qwen2.5-3b-behavior-binding-v1/materials/inputs.json')
    mapping = read('runs/qwen2.5-3b-behavior-binding-v1/coordinator/behavior_mapping.json')
    ratings = {r['item_id']:r for r in read('docs/records/2026-10-21-behavior-binding-results-ratings.json')['ratings']}
    b_i = [r for r in bmat if r['condition']=='I']
    check(len(b_i)==24 and all(ratings[mapping[r['id']]]['has_substantive_target_answer']=='no'
          and ratings[mapping[r['id']]]['adopts_cell_distractor_value']=='no' for r in b_i), 'Binding I counts differ')
    check(all(ratings[mapping[r['id']]]['claimed_evidence_supports_target']=='unknown' for r in bmat),
          'Old evidence-attribution unknown changed')
    tpred = {r['id']:r for r in read('runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/predictions.json')['records']}
    packet = {r['item_id']:r for r in read('runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/behavior_review/packet.json')['items']}
    tmap = read('runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1/coordinator/behavior_mapping.json')
    bpred = {r['id']:r for r in read('runs/qwen2.5-3b-behavior-binding-v1/predictions.json')['records']}
    groups = {
        'transfer_all_I60': [(packet[tmap[r['id']]]['documents'],tpred[r['id']]['input_tokens']) for r in irows],
        'transfer_selected_answering_I23': [(packet[tmap[r['id']]]['documents'],tpred[r['id']]['input_tokens']) for r in selected],
        'transfer_matched_S23_unfiltered_for_S_behavior': [(packet[tmap[r['id'][:-1]+'S']]['documents'],tpred[r['id'][:-1]+'S']['input_tokens']) for r in selected],
        'binding_all48': [(r['docs'],bpred[r['id']]['input_tokens']) for r in bmat],
        'binding_I24': [(r['docs'],bpred[r['id']]['input_tokens']) for r in b_i]}
    stats = table(P+'-statistics.csv')
    check(len(stats)==5, 'Wrong statistics slices')
    for row in stats:
        group = groups[row['group']]
        tokens = [n for docs,n in group]
        lengths = [sum(len(s) for s in docs) for docs,n in group]
        expected = dict(rows=len(group), document_slots=sum(len(ds) for ds,n in group),
            unique_document_texts=len({s for ds,n in group for s in ds}),
            input_tokens_min=min(tokens), input_tokens_max=max(tokens), input_tokens_sum=sum(tokens),
            input_tokens_mean=sum(tokens)/len(tokens), document_chars_min=min(lengths),
            document_chars_max=max(lengths), document_chars_mean=sum(lengths)/len(lengths))
        check(all(float(row[k])==v for k,v in expected.items()), 'Statistics differ: '+row['group'])
    design = read('prompts/behavior_relation_attachment_design_v1.json')
    samples = read(P+'-samples.json')['items']
    by_id = {r['id']:r for r in samples}
    worlds = {r['id']:r['worlds'] for r in read(P+'-worlds.json')['items']}
    author = read(P+'-author-review.json')
    author_rows = {r['id']:r for r in author['rows']}
    check(len(samples)==len(by_id)==len(author_rows)==16 and set(by_id)==set(author_rows), 'Example/author coverage differs')
    facts = {}
    for row in samples:
        sid,cell,variant = row['id'].split('_')
        spec = next(s for s in design['example_scenarios'] if s['id']==sid)
        query = row['question'].split('what ',1)[1].split(' is assigned',1)[0]
        matches = []
        for idx,doc in enumerate(row['documents']):
            # Different parser from the artifact builder; read relation arguments from text.
            if doc.startswith('The ') and ' assigned to Unit ' in doc:
                lhs,rest = doc[4:].split(' assigned to Unit ',1)
                owner,rest = rest.split(' is ',1)
                value,rest = rest.split('. Unit ',1)
                nonowner = rest.split(' has a ledger entry.',1)[0]
                matches.append((idx,lhs,owner,value,nonowner))
        check(len(matches)==1, 'Missing/duplicate displayed assignment')
        idx,attr,owner,value,nonowner = matches[0]
        check(idx+1==spec['candidate_slot'] and value==spec[variant]
              and {owner,nonowner}=={spec['target'],spec['other']}, 'Displayed relation differs')
        check(query==spec['queried_attribute'] and len(row['documents'])==5, 'Wrong query/slots')
        background = [d for i,d in enumerate(row['documents']) if i!=idx]
        check(background==[d.format(**spec) for d in design['background_templates_in_order']], 'Background differs')
        check(re.findall(r'K-\d{5}','\n'.join([row['question']]+row['documents']))==[value], 'Code leakage')
        supported = owner==spec['target'] and attr==query
        check(supported==(cell=='TQ') and author_rows[row['id']]['author_mode']==('answer' if supported else 'refuse'),
              'Author relation judgment differs')
        facts[row['id']] = (owner,attr,value)
        if not supported:
            check(row['id'] in worlds and len(worlds[row['id']])==2, 'Missing compatible worlds')
            assignments = [{(x['entity'],x['attribute']):x['value'] for x in w} for w in worlds[row['id']]]
            domain = set(itertools.product((spec['target'],spec['other']),('access code','inspection code')))
            for w in assignments:
                check(set(w)==domain and w[(owner,attr)]==value, 'Incompatible world')
            a,b = assignments
            check({k for k in a if a[k]!=b[k]}=={(spec['target'],query)}, 'Wrong world difference')
        else:
            check(row['id'] not in worlds, 'Supported example with I witnesses')
    check(len(worlds)==12, 'Wrong I world count')
    pairs = table(P+'-pairs.csv')
    check(len(pairs)==24 and len({(r['left'],r['right']) for r in pairs})==24, 'Duplicate/missing pairs')
    primary = [r for r in pairs if r['kind']=='primary_entity_other_attribute']
    check(len(primary)==4, 'Wrong primary-pair count')
    for pair in pairs:
        left,right = by_id[pair['left']],by_id[pair['right']]
        changed = [i+1 for i,(a,b) in enumerate(zip(left['documents'],right['documents'])) if a!=b]
        check(left['question']==right['question'] and changed==[int(pair['changed_slot'])], 'Uncontrolled pair')
        if pair in primary:
            check(left['cell']=='TA' and right['cell']=='OA', 'Primary comparison differs')
            for row in (left,right):
                check(facts[row['id']][1]!=next(s for s in design['example_scenarios'] if s['id']==row['scenario'])['queried_attribute'],
                      'Primary endpoint has queried field')
            words = lambda r: Counter(re.findall(r'\w+',' '.join(r['documents'])))
            check(words(left)==words(right), 'Primary mention multiset differs')
    result = dict(status='independent_numeric_and_structural_verification_passed',
        independent_semantic_review=False, preserved_files=len(preserved), old_complete_I=60,
        old_answering=23, binding_I=24, binding_I_answering=0, old23_joins=23,
        statistics_slices=5, maximum_statistics_error=0, examples=16,
        complete_compatible_worlds=24, pairs=24, primary_example_pairs=4,
        author_review_rows=16, new_gpu=0, new_fits=0,
        source_sha256={p:sha(p) for p in ['scripts/verify_behavior_structure_audit.py',
            P+'.json', P+'-samples.json', P+'-worlds.json', P+'-author-review.json', P+'-pairs.csv']})
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
