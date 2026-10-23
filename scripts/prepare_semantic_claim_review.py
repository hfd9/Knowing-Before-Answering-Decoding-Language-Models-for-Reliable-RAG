"""Assemble existing evidence for independent claim review; stdlib, no new scoring."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = 'prompts/semantic_claim_review_preparation_v1.json'
OLD = 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1'
NEW = 'runs/qwen2.5-3b-relation-attachment-v1'
AUDIT = 'docs/records/2026-10-21-insufficient-answer-audit.json'
BEHAVIOR = 'docs/records/2026-10-21-semantic-transfer-exploratory-behavior'
RELATION = 'docs/records/2026-10-23-relation-attachment-results'
SEAL = 'docs/records/2026-10-21-semantic-transfer-exploratory-retrain-fit-seal.json'
BUDGET = 'runs/semantic-transfer-shared-one-fit-budget-v1.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest((ROOT / path).read_bytes())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def reference(text, snippet=None, document_index=None):
    snippet = text if snippet is None else snippet
    start = text.find(snippet)
    require(start >= 0 and text.count(snippet) == 1, 'Missing/ambiguous reference')
    result = dict(start=start, end=start + len(snippet), quote=snippet,
                  text_sha256=digest(text.encode()))
    if document_index is not None:
        result['document_index'] = document_index
    return result


def units(answer):
    """Mechanical sentence spans only; no atomicity or entailment inference."""
    boundaries = [0] + [m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z\"])', answer)] + [len(answer)]
    result = []
    for start, end in zip(boundaries, boundaries[1:]):
        text = answer[start:end]
        require(bool(text.strip()), 'Empty candidate unit')
        result.append(dict(unit_id=f'U{len(result)+1:02d}', **reference(answer, text)))
    require(''.join(u['quote'] for u in result) == answer, 'Sentence coverage mismatch')
    return result


def csv_bytes(rows, columns):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    writer.writerows({c: r[c] if not isinstance(r[c], (list, dict)) else
                     json.dumps(r[c], ensure_ascii=False) for c in columns} for r in rows)
    return out.getvalue().encode()


def archive(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_STORED) as target:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 10, 23, 0, 0, 0))
            entry.external_attr = 0o644 << 16
            target.writestr(entry, data)
    return buf.getvalue()


INSTRUCTIONS = """# 逐主张语义审查说明

本包包含55条既有问答，每条保留完整问题、五篇文档和原始回答。
这是按具体研究问题选取的案例包，不能估计总体发生率；多条输入可能来自同一底题。

先只打开第一阶段输入包：填写上下文暴露表，完整阅读每条五篇文档，记录问题的目标、可能答案、缺失关系、矛盾及题意歧义。
原始文档存在截取、改写或措辞问题时按实际呈现文本评审，不擅自补成完整来源。
先另存输入判断副本，保留其文件SHA256与完成时间，再领取第二阶段原始回答包。
输入判断若在查看回答后修订，保留旧版，并记录修订理由、时间与暴露情况。
当前交付还未实际发送给评审；两阶段文件同时存放不等于完成了输入先封存流程。

第二阶段须独立记录两个端点：

1. 是否给出具体目标答案、该目标答案有何文档依据；没有给答案时，所述缺口是否准确。
2. 回答每项解释性主张是否有据，包括存在/缺失事实、冲突、引用归属、因果、分类、范围与指代。

不作答不自动使解释正确；目标答案正确也不自动使全文每项主张正确。
按原回答拆分可分别核验的原子主张。模板中的逐句候选单元只是机械文本切分，可能含多项主张；请拆分、补全并保留原字符引用，不能直接当原子标签。
每项填写claim、document_support、missing_link、ambiguity；记录支持和反向证据的文档编号、逐字引文、字符起止（左闭右开）。
支持判断可为supported、contradicted、unsupported、ambiguous或not_applicable。留空是未审，ambiguous是已审但不能确定；两者不可混同。
无直接句子不等于不能合理推导。逐字引文匹配也不等于蕴含主张。对否认信息存在、声称有冲突等全局主张，必须核对全部五篇文档；具体互斥命题应明确写出。
区分所问关系、实体、属性、时间、修饰范围、语言词义和外部世界事实；不要把无据回答直接归因于参数记忆或内部机制。
若必须借助常识或外部事实，明确记录该依赖，不以外部知识替代提供文本的支持关系。本次准备未作外部检索。

所有模板评分初始为null。请填写副本，不覆盖空白模板。原子主张可增删，最终须声明已覆盖完整回答。
匿名编号不能保证独立性；相似材料与任务结构可能揭示关系。若接触过项目历史、作者判断、结果或协调者资料，完整申报，不能自称独立盲评。
不要访问仓库交接入口、历史结果、协调者目录、模型/probe或保留底题。不得根据未知标签反向补全答案。
材料准备、程序校验、文件哈希及另一个模型会话均不等于实际独立语义审核通过。
"""


def artifacts():
    spec = read(SPEC)
    base_dir = spec['delivery']['directory']
    source_paths = [SPEC, AUDIT, BEHAVIOR+'-cells.csv', BEHAVIOR+'-ratings.json',
                    RELATION+'-manual.json', RELATION+'-ratings.json', SEAL, BUDGET,
                    OLD+'/approved_labels.json', OLD+'/behavior_review/packet.json',
                    OLD+'/coordinator/behavior_mapping.json', OLD+'/predictions.json',
                    NEW+'/behavior_review/packet.json', NEW+'/coordinator/behavior_mapping.json',
                    NEW+'/predictions.json', 'scripts/prepare_semantic_claim_review.py']
    seal = read(SEAL)
    source_paths += sorted(seal['files'])
    source_paths = sorted(set(source_paths))
    source_hashes = {p: sha(p) for p in source_paths}
    require(all(sha(p) == h for p, h in seal['files'].items()), 'Fit seal changed')
    require(seal['remaining_original_design_fits'] == 0 and seal['fit_attempts'] == 1,
            'Unexpected original fit budget')
    require(all(v is None for v in read(OLD+'/approved_labels.json').values()), 'Formal labels changed')
    require(read(BUDGET)['maximum_attempts'] == 1, 'Shared budget changed')
    audits = {r['id']: r for r in read(AUDIT)['cases']}
    require(len(audits) == 23, 'Anchor mismatch')
    with (ROOT / (BEHAVIOR+'-cells.csv')).open(newline='') as handle:
        old_rows = list(csv.DictReader(handle))
    old_by_id = {r['id']: r for r in old_rows}
    frozen_selection = {r['id'] for r in old_rows
                        if r['exposed_author_input_mode'] == 'refuse' and r['has_substantive_answer'] == 'yes'}
    require(set(audits) == frozen_selection, 'Original 23 selection mismatch')
    bases = {old_by_id[k]['original_id'] for k in audits}
    selected = [r for r in old_rows if r['original_id'] in bases and r['condition'] in ['I', 'S']]
    require(len(bases) == 13 and len(selected) == 52, 'Control selection mismatch')
    require(sorted({r['id'].split('_')[0] for r in selected}) == spec['selection']['old_base_prefixes'],
            'Base selection differs from fixed scope')
    packets, mappings, predictions = {}, {}, {}
    for family, run in [('old', OLD), ('relation', NEW)]:
        packets[family] = {r['item_id']: r for r in read(run+'/behavior_review/packet.json')['items']}
        mappings[family] = read(run+'/coordinator/behavior_mapping.json')
        predictions[family] = {r['id']: r for r in read(run+'/predictions.json')['records']}
        require(len(mappings[family]) == len(packets[family]) == len(predictions[family])
                and set(mappings[family].values()) == set(packets[family]), 'Source bijection mismatch')
    ratings = {r['item_id']: r for r in read(BEHAVIOR+'-ratings.json')['ratings']}
    relation_ratings = {r['item_id']: r for r in read(RELATION+'-ratings.json')['ratings']}
    relation_notes = {r['item_id']: r for r in read(RELATION+'-manual.json')['posthoc_qualitative_notes_not_frozen_endpoints']
                      if r['kind'] == 'unsupported_conflict_statement'}
    keys = [('old', r['id']) for r in selected] + [('relation', k) for k in spec['selection']['new_explanation_ids']]
    keys.sort(key=lambda pair: digest(('seed42|'+'|'.join(pair)).encode()))
    require(len(keys) == len(set(keys)) == 55, 'Packet size mismatch')
    input_items, output_items, input_forms, output_forms, cases, inventory = [], [], [], [], [], []
    notes_md = ['# 协调者逐项索引：既有判断与待审主张', '',
                '勿交给独立评审。所有评价均复制既有有历史暴露的作者判断，不新增语义评分。',
                '主张候选按原句机械列出，尚未完成逐原子主张的独立语义审查。',
                '23条锚点的8/9/6类别仅为旧文本现象分类；对照保留原失败与unknown。',
                '“未识别特定边界”不表示独立确定无歧义；S/I是旧构造角色，不是本包新金标签。', '']
    for number, (family, key) in enumerate(keys, 1):
        iid = f'Q{number:03d}'
        source_item = packets[family][mappings[family][key]]
        answer = source_item['answer']
        require(answer == predictions[family][key]['raw_output'], 'Original answer mismatch: '+key)
        require(len(source_item['documents']) == 5, 'Five-document set required')
        docs = source_item['documents']
        question = source_item['question']
        input_items.append(dict(item_id=iid, question=question, documents=docs))
        sentence_units = units(answer)
        output_items.append(dict(item_id=iid, answer=answer, candidate_sentence_units=sentence_units))
        input_forms.append(dict(item_id=iid, status='unreviewed', target_interpretation=None,
                                answerability=None, candidate_answer=None, document_support=None,
                                missing_link=None, ambiguity=None, conflicting_propositions=None))
        output_forms.append(dict(item_id=iid, status='unreviewed',
            gives_specific_target_answer=None, target_claim_supported=None, withholding_matches_gap=None,
            explanation_all_claims_supported=None, full_answer_claim_coverage_confirmed=None,
            claim_reviews=[dict(unit_id=u['unit_id'], source_span=u, atomic_claims=None,
                               document_support=None, counterevidence=None, missing_link=None,
                               ambiguity=None, judgment=None) for u in sentence_units]))
        for j, doc in enumerate(docs, 1):
            inventory.append(dict(item_id=iid, document_index=j, sha256=digest(doc.encode())))
        if family == 'old':
            row = old_by_id[key]
            require(row['question'] == question and row['raw_output'] == answer, 'Old CSV join mismatch')
            prior = ratings[row['item_id']]
            group = 'old_23_answer_anchors' if key in audits else (
                'same_base_I_nonanswer_control' if row['condition'] == 'I' else 'same_base_S_control')
            if group == 'same_base_I_nonanswer_control':
                require(row['has_substantive_answer'] == 'no', 'Expected related nonanswer')
            related = audits.get(key)
            if related is None:
                related = audits.get(key.rsplit('_', 1)[0]+'_I')
            if related is None:
                related = next(a for a in audits.values() if a['original_id'] == row['original_id'])
            require(prior['rationale'] == row['rationale'], 'Prior rationale mismatch')
            if key in audits:
                anchor = audits[key]
                focal = dict(claim=anchor['unsupported_claim'],
                             output_reference=anchor['critical_output_citation'],
                             supplied_facts=anchor['supplied_facts'],
                             missing_link=anchor['required_fact'],
                             assessment=anchor['assessment'], ambiguity=anchor['boundary'],
                             prior_surface_pattern=anchor['primary_pattern'],
                             source=AUDIT, source_pointer='/cases/'+str(list(audits).index(key)))
            else:
                focal = dict(claim=answer, output_reference=reference(answer),
                             supplied_facts='参见下列原评分引用及完整五文档；不从S/I角色推断每项主张有据。',
                             missing_link='既有评分理由见assessment；未曾逐原子审查的缺失环节保持待审。',
                             assessment=prior['rationale'],
                             ambiguity='既有理由及原unknown原样保留；完整主张支持/缺失/歧义尚待独立审查。',
                             prior_surface_pattern=None, source=BEHAVIOR+'-ratings.json',
                             source_item_id=row['item_id'])
            context_refs = []
            for ref in prior['input_citations']:
                d = docs[ref['document_index']-1]
                require(d[ref['start']:ref['end']] == ref['quote'], 'Old reference offset mismatch')
                context_refs.append(reference(d, ref['quote'], ref['document_index']))
            pairing = key.rsplit('_', 1)[0] + ('_S' if row['condition']=='I' else '_I')
            prior_fields = {k: prior[k] for k in ['has_substantive_answer', 'acknowledges_insufficiency',
                            'acknowledges_conflict', 'answer_grounded_correct']}
            original_id, condition = row['original_id'], row['condition']
            related_question = related['required_fact']
        else:
            group, original_id, condition, pairing = 'new_3_explanation_cases', key.split('_')[0], key.split('_')[1], None
            prior = relation_ratings[source_item['item_id']]
            note = relation_notes[source_item['item_id']]
            focal = dict(claim=note['quote'], output_reference=reference(answer, note['quote']),
                         supplied_facts='完整五文档及独立字段规则如下；匹配引文不等于存在互斥命题。',
                         missing_link='需要同一实体、同一属性、同一范围内不相容的命题；是否存在由评审检查整个文档集。',
                         assessment=note['assessment'],
                         ambiguity='此为旧事后冲突解释观察，仍待实际独立核验；不因主行为不答而认定解释正确。',
                         prior_surface_pattern=None, source=RELATION+'-manual.json',
                         source_item_id=source_item['item_id'])
            context_refs = [reference(d, document_index=j) for j,d in enumerate(docs,1)]
            prior_fields = {k: prior[k] for k in ['has_substantive_target_answer',
                'adopts_displayed_candidate_as_requested_target_value', 'supported_target_answer',
                'acknowledges_missing_target_attribute']}
            related_question = question
        case = dict(item_id=iid, source_family=family, source_id=key,
                    source_item_id=source_item['item_id'], selection_group=group,
                    original_id=original_id, original_condition=condition, paired_source_id=pairing,
                    question=question, required_relation_context=related_question, full_answer=answer,
                    focal_prior_author_audit=focal, prior_document_context_references=context_refs,
                    prior_behavior_fields=prior_fields, prior_behavior_rationale=prior['rationale'],
                    candidate_sentence_units=sentence_units, independent_review_status='not_started',
                    limitation='旧作者整体理由不替代逐主张审查；每句可含多命题，所有主张仍需独立拆分与判断。')
        cases.append(case)
        notes_md += [f'## {iid} / {key} / {group}', '', f'问题：{question}', '',
                     f'所问关系：{related_question}', '', '完整回答：', '', answer, '',
                     '既有作者关注主张：'+focal['claim'], '',
                     '已有文本/背景：'+focal['supplied_facts'], '',
                     '所需或缺失环节：'+focal['missing_link'], '',
                     '既有判断（有暴露，待独立核验）：'+focal['assessment'], '',
                     '歧义/边界：'+focal['ambiguity'], '',
                     '原行为评分理由：'+prior['rationale'], '',
                     '文档引用（仅定位原文，不自动认证对每项主张的支持）：', '']
        notes_md += [f"- D{r['document_index']} [{r['start']},{r['end']})：{r['quote']}" for r in context_refs]
        notes_md += ['', '完整回答的逐句候选主张（均待拆分与独立判断）：', '']
        notes_md += [f"- {u['unit_id']} [{u['start']},{u['end']})：{u['quote'].rstrip()}" for u in sentence_units]
        notes_md += ['']
    counts = dict(Counter(c['selection_group'] for c in cases))
    require(counts == dict(old_23_answer_anchors=23, same_base_I_nonanswer_control=3,
                           same_base_S_control=26, new_3_explanation_cases=3), 'Wrong group counts')
    files = {}
    def put(name, value):
        files[base_dir+'/'+name] = value if isinstance(value, bytes) else value.encode()
    put('public/INSTRUCTIONS.md', INSTRUCTIONS)
    put('public/input_packet.json', encoded(dict(items=input_items)))
    put('public/output_packet.json', encoded(dict(items=output_items)))
    input_md = ['# 第一阶段：问题与五文档全文', '']
    output_md = ['# 第二阶段：原始回答全文', '']
    for item, out in zip(input_items, output_items):
        input_md += ['## '+item['item_id'], '', item['question'], '']
        for j, doc in enumerate(item['documents'], 1):
            input_md += ['### Document '+str(j), '', doc, '']
        output_md += ['## '+out['item_id'], '', out['answer'], '']
    put('public/input_packet.md', '\n'.join(input_md))
    put('public/output_packet.md', '\n'.join(output_md))
    put('public/input_review_template.json', encoded(dict(reviewer_id=None, items=input_forms)))
    put('public/claim_review_template.json', encoded(dict(reviewer_id=None,
        sealed_input_review_sha256=None, sealed_input_review_completed_at=None, items=output_forms)))
    put('public/reviewer_context_template.json', encoded(dict(reviewer_id=None, reviewed_at=None,
        prior_project_history_exposure=None, prior_author_ratings_exposure=None,
        prior_outputs_or_probe_results_exposure=None, coordinator_material_exposure=None,
        instructions_or_hidden_context_exposure=None, exposure_description=None,
        input_first_process_actually_followed=None, actual_independence_determination=None)))
    put('coordinator/cases.json', encoded(dict(history_exposed=True, independent_gold=False,
        new_scores=0, actual_independent_reviews=0, selection_group_counts=counts, cases=cases)))
    put('coordinator/cases.md', '\n'.join(notes_md))
    table = [dict(item_id=c['item_id'], source_id=c['source_id'], selection_group=c['selection_group'],
                  claim=c['focal_prior_author_audit']['claim'],
                  document_support_context=c['prior_document_context_references'],
                  missing_link=c['focal_prior_author_audit']['missing_link'],
                  ambiguity=c['focal_prior_author_audit']['ambiguity'],
                  prior_author_assessment=c['focal_prior_author_audit']['assessment']) for c in cases]
    put('coordinator/four_axes.csv', csv_bytes(table, list(table[0])))
    pairs = [dict(source_I_id=r['id'], source_S_id=r['id'][:-1]+'S', original_id=r['original_id'],
                  expression=r['expression']) for r in selected if r['condition']=='I']
    put('coordinator/pairs.json', encoded(dict(pairs=pairs)))
    put('coordinator/document_inventory.json', encoded(dict(slots=inventory,
        unique_texts=len({r['sha256'] for r in inventory}), declaration='复制/哈希核对，不声明本轮重新全文语义评分。')))
    put('README.md', '# 独立语义审查材料准备完成；实际独立审核尚未进行\n\n'
        '固定55条：23旧缺证作答锚点＋同13底题的3条I未作答＋26条S对照＋3条新冲突解释。'
        '保留两表达和全部失败/unknown对照；其余34条旧I仍属原60完整分母，未纳入最小案例包。\n\n'
        '先交 reviewer-inputs.zip，实际封存输入判断后再交 reviewer-outputs.zip。'
        '当前仅准备，两阶段ZIP均在本地，未外发；没有审核员、审核结果或独立批准。\n\n'
        'public供评审；coordinator含选择映射、作者既有判断和逐句候选主张，勿交给评审。'
        '所有新审查字段为null，旧判断复制不变，不能视作本次评分。'
        '原目标回答端点与解释逐主张支持端点分开；拒绝答案并不保证解释有据。\n\n'
        '三条新冲突解释待独立核验；旧8/9/6不解释内部机制。'
        'S构造对照不保证输出正确；两条Khet充分对照拒答、名称归属和位置范围unknown均保留。\n\n'
        '本轮按既定上限收尾；无采集/前向/拟合/补probe/patching，380底题保持封存。'
        '只有实际独立审查后再决定一个具体问题是否值得继续，不自动启动实验。\n')
    for phase, names in [
        ('inputs', ['INSTRUCTIONS.md', 'input_packet.json', 'input_packet.md',
                    'input_review_template.json', 'reviewer_context_template.json']),
        ('outputs', ['INSTRUCTIONS.md', 'output_packet.json', 'output_packet.md', 'claim_review_template.json'])]:
        put('reviewer-'+phase+'.zip', archive({name: files[base_dir+'/public/'+name] for name in names}))
    manifest = dict(status='prepared_not_independently_reviewed', items=55, old_base_count=13,
        counts=counts, document_slots=len(inventory), unique_document_texts=len({r['sha256'] for r in inventory}),
        sentence_candidate_units=sum(len(r['candidate_sentence_units']) for r in output_items),
        actual_independent_reviews=0, new_semantic_scores=0, new_model_calls=0, new_fits=0,
        remaining_original_design_fits=0, formal_gate=False, formal_labels_added=0,
        held_out_380_accessed=False, source_sha256=source_hashes,
        payload_sha256={p: digest(b) for p,b in sorted(files.items())},
        note='Sentence spans are text units, not atomic semantic scores. Input-first and independence checks are prepared workflows, not completed audits.')
    put('manifest.json', encoded(manifest))
    return files, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['build', 'verify'], required=True)
    args = parser.parse_args()
    files, manifest = artifacts()
    for path, data in files.items():
        target = ROOT / path
        if args.stage == 'build':
            require(not target.exists() or target.read_bytes() == data, 'Refuse changed artifact: '+path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        else:
            require(target.read_bytes() == data, 'Artifact replay mismatch: '+path)
    require(all(sha(p) == h for p,h in manifest['source_sha256'].items()), 'Source changed during preparation')
    print(json.dumps(dict(stage=args.stage, items=manifest['items'], counts=manifest['counts'],
                         document_slots=manifest['document_slots'],
                         candidate_units=manifest['sentence_candidate_units'],
                         source_files_preserved=len(manifest['source_sha256']),
                         artifacts=len(files), independent_reviews=0, new_scores=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
