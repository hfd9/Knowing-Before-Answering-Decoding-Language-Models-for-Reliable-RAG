"""Replay exposed author judgments and seal v5 delivery artifacts; no model or label approval."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import semantic_transfer_review_intake as intake

ROOT = intake.ROOT
MATERIALS = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v5'
PARENT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v4-r2'
DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-v5-acceptance-v1'
PREFIX = ROOT / 'docs/records/2026-10-21-semantic-transfer-v5-acceptance'
RATINGS = Path(str(PREFIX) + '-ratings.json')
PRESERVED = Path(str(PREFIX) + '-preserved.json')
OLD_RATINGS = ROOT / 'docs/records/2026-10-20-semantic-transfer-author-input-review-ratings.json'
read, digest, require, serialize = intake.read, intake.digest, intake.require, intake.serialize


def bytes_for(value):
    if isinstance(value, bytes):
        return value
    return (value if isinstance(value, str) else serialize(value)).encode('utf-8')


def put(path, value, write):
    expected = bytes_for(value)
    if path.exists():
        require(path.read_bytes() == expected, f'Frozen acceptance artifact differs: {path}')
    elif write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
    else:
        raise ValueError(f'Missing acceptance artifact: {path}')


def csv_text(rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            for k, v in row.items()})
    return output.getvalue()


def archive(members):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, content in sorted(members.items()):
            require(not name.startswith('/') and '..' not in Path(name).parts, 'Unsafe archive member')
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, bytes_for(content))
    return stream.getvalue()


def validate(rows, value):
    require(value['history_exposed'] is True and value['independent_gold'] is False
        and value['approved_for_training'] is False and value['gpu_launch_ready'] is False,
        'Exposed review cannot approve labels or claim independence')
    require(value['source_protocol_sha256'] == digest(MATERIALS / 'protocol.json')
        and value['inputs_sha256'] == digest(MATERIALS / 'materials/inputs.json'), 'Wrong v5 review batch')
    require(len(value['ratings']) == len({r['id'] for r in value['ratings']}) == len(rows) == 240,
        'Exactly240 unique judgments required')
    ratings = {r['id']: r for r in value['ratings']}
    require(set(ratings) == {r['id'] for r in rows}, 'Review ID mismatch')
    require(len(value['base_reviews']) == 30, 'All30 base reviews required')
    bases = {b['original_id']: b for b in value['base_reviews']}
    require(len(bases) == 30 and set(bases) == {r['original_id'] for r in rows}, 'Base review mismatch')
    documents, backgrounds = {}, []
    parent = {r['id']: r for r in read(PARENT / 'materials/inputs.json')}
    order = [f'{e}_{c}' for e in ['A', 'B'] for c in ['S', 'K', 'I', 'C']]
    for row in rows:
        require(row['semantic_label'] is None, 'Formal semantic labels must remain null')
        rating, base, old = ratings[row['id']], bases[row['original_id']], parent[row['id']]
        for key in ['id', 'original_id', 'partition', 'expression', 'condition']:
            require(rating[key] == row[key], 'Review identity mismatch')
        require(row['question'] == old['question'] and row['target_slots'] == old['target_slots']
            and row['partition'] == old['partition'], 'Frozen question/slot/partition changed')
        require(rating['semantic_mode'] in intake.MODES, 'Unknown semantic mode')
        require(rating['confidence'] in {'high', 'moderate', 'ambiguous'}, 'Confidence missing')
        require(rating['independent_gold'] is False and rating['approved_for_training'] is False,
            'Judgment cannot approve labels')
        require(rating['rationale'].strip() and rating['required_relation'].strip(), 'Explicit reasoning missing')
        for mode, field in [('answer', 'support_chain'), ('refuse', 'missing_facts'), ('conflict', 'conflicting_claims')]:
            if rating['semantic_mode'] == mode:
                require(bool(rating[field]) and (mode != 'conflict' or len(rating[field]) >= 2), 'Semantic evidence missing')
        citations = rating['citations']
        require(len(citations) == 2 and {c['doc_slot'] for c in citations} == set(row['target_slots']),
            'Both complete target passages must be cited once')
        for citation in citations:
            doc = row['docs'][citation['doc_slot'] - 1]
            start, end = citation['start'], citation['end']
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(doc), 'Invalid citation offsets')
            require(doc[start:end] == citation['quote'] and citation['document_sha256'] == hashlib.sha256(doc.encode()).hexdigest(),
                'Citation mismatch')
        require(rating['semantic_mode'] == base['modes'][order.index(row['expression'] + '_' + row['condition'])],
            'Explicit base/row judgment mismatch')
        require(base['question'] == row['question'] and base['partition'] == row['partition'], 'Base scope mismatch')
        require(base['S_to_I_status'] in {'unknown_support_scope', 'provisionally_acceptable_relation_projection'}, 'Missing S/I audit')
        require(base['literal_single_atom_minimality_proved'] is False and base['new_unrelated_fact_identified'] is False,
            'Current manual review reports no newly unrelated fact, not a formal proof')
        for key in ['support_review', 'missing_review', 'conflict_review', 'removed_relation', 'retained_facts_review']:
            require(bool(base[key].strip()), 'Base reasoning incomplete')
        require(base['backgrounds_reread_in_full'] is True and len(base['background_assessments']) == 3,
            'Background reading declaration incomplete')
        require({int(s.split(':')[0]) for s in base['background_assessments']} == set(range(1, 6)) - set(row['target_slots']),
            'Background slot reasoning mismatch')
        for slot, doc in enumerate(row['docs'], 1):
            sha = hashlib.sha256(doc.encode()).hexdigest()
            documents.setdefault(sha, dict(characters=len(doc), occurrences=[]))['occurrences'].append(dict(id=row['id'], slot=slot))
            if slot not in row['target_slots']:
                require(doc == old['docs'][slot - 1], 'Background changed')
                if row['expression'] == 'A' and row['condition'] == 'S':
                    backgrounds.append(dict(original_id=row['original_id'], doc_slot=slot, document_sha256=sha,
                        assessment=next(s for s in base['background_assessments'] if s.startswith(str(slot) + ':'))))
    require(value['reviewed_document_slots'] == sum(len(d['occurrences']) for d in documents.values()) == 1200
        and value['reviewed_unique_full_documents'] == len(documents) == 435, 'Reading inventory mismatch')
    require(len(backgrounds) == 90, 'All90 background slots required')
    return ratings, bases, dict(reading_is_reviewer_declaration_not_proved_by_hash=True,
        document_slots=1200, unique_full_documents=len(documents), documents=documents,
        background_slots=backgrounds, unique_background_documents=len({b['document_sha256'] for b in backgrounds}))


def derive(rows, value):
    ratings, bases, inventory = validate(rows, value)
    old_reviews = read(OLD_RATINGS)['base_decisions']
    old_modes = {r['id']: r['semantic_mode'] for r in read(OLD_RATINGS)['ratings']}
    parent = {r['id']: r for r in read(PARENT / 'materials/inputs.json')}
    tokens = read(MATERIALS / 'preflight.json')['input_tokens']
    cells = [dict(**ratings[r['id']], question=r['question'], changed_from_v4=r['docs'] != parent[r['id']]['docs'],
        input_tokens=tokens[r['id']], formal_semantic_label=r['semantic_label'],
        probe_prediction=None, generated_answer=None) for r in rows]
    pairs, repairs = [], []
    for oid, base in bases.items():
        g = {(r['expression'], r['condition']): r for r in rows if r['original_id'] == oid}
        contrasts = [('AB_' + c, ('A', c), ('B', c)) for c in ['S', 'K', 'I', 'C']]
        contrasts += [(e + '_S_to_' + c, (e, 'S'), (e, c)) for e in ['A', 'B'] for c in ['K', 'I', 'C']]
        for name, left, right in contrasts:
            a, b = g[left], g[right]
            la, lb = ratings[a['id']]['semantic_mode'], ratings[b['id']]['semantic_mode']
            if name.startswith('AB_'):
                detail = base['AB_caveats'].get(left[1])
                status = 'residual_detail_or_scope_caveat' if detail else 'no_specific_AB_difference_identified'
                reasoning = detail or '本轮未识别具体额外命题差异；这不是形式等价或独立确认。'
                removed, retained = '', ''
            elif right[1] == 'I':
                status, reasoning = base['S_to_I_status'], base['missing_review']
                removed, retained = base['removed_relation'], base['retained_facts_review']
            else:
                status = 'descriptive_conflict_identified' if right[1] == 'C' else (
                    'question_obligation_scope_unknown' if la == 'unknown' or lb == 'unknown' else 'compatible_support_identified')
                reasoning = base['conflict_review'] if right[1] == 'C' else base['support_review']
                removed, retained = '', ''
            pairs.append(dict(original_id=oid, partition=a['partition'], contrast=name, left_id=a['id'], right_id=b['id'],
                left_mode=la, right_mode=lb, determinate=la != 'unknown' and lb != 'unknown',
                left_target_citations=ratings[a['id']]['citations'], right_target_citations=ratings[b['id']]['citations'],
                status=status, rationale=reasoning, removed_relation=removed, retained_facts_review=retained,
                input_token_delta=tokens[b['id']] - tokens[a['id']],
                literal_single_atom_minimality_proved=False, formal_AB_equivalence_proved=False,
                independent_gold=False, probe_prediction=None, probability_delta=None))
        for condition, old_issue in old_reviews[oid].get('expression_caveats', {}).items():
            a, b = g['A', condition], g['B', condition]
            detail = base['AB_caveats'].get(condition, '')
            status = ('descriptive_alignment_repaired_obligation_scope_still_unknown' if base['base_id'] == 'stv17'
                else 'old_specific_difference_repaired_other_detail_remains' if detail else 'old_specific_difference_repaired_in_author_review')
            repairs.append(dict(original_id=oid, condition=condition, old_issue=old_issue,
                left_id=a['id'], right_id=b['id'], status=status, residual_detail=detail,
                current_target_citations=ratings[a['id']]['citations'] + ratings[b['id']]['citations'],
                independent_repair_confirmation=False))
    ab = [p for p in pairs if p['contrast'].startswith('AB_')]
    si = [p for p in pairs if p['contrast'].endswith('S_to_I')]
    caveats = [p for p in ab if p['status'] == 'residual_detail_or_scope_caveat']
    summary = dict(status='v5_exposed_author_acceptance_complete_with_residual_risks_sealed_no_GPU',
        reviewed_bases=30, reviewed_cells=240, changed_cells=sum(c['changed_from_v4'] for c in cells),
        reviewed_document_slots=1200, reviewed_unique_full_documents=len(inventory['documents']),
        manual_semantic_counts=dict(Counter(c['semantic_mode'] for c in cells)),
        unknown_ids=[c['id'] for c in cells if c['semantic_mode'] == 'unknown'],
        semantic_mode_changes_from_v4=[dict(id=c['id'], before=old_modes[c['id']],
            after=c['semantic_mode']) for c in cells if c['semantic_mode'] != old_modes[c['id']]],
        partitions={part: dict(planned=sum(c['partition'] == part for c in cells),
            counts=dict(Counter(c['semantic_mode'] for c in cells if c['partition'] == part)))
            for part in ['semantic_train', 'semantic_dev', 'semantic_eval']},
        S_to_I_pairs=dict(total=len(si), statuses=dict(Counter(p['status'] for p in si)),
            reviewed_answer_to_refuse=sum(p['left_mode'] == 'answer' and p['right_mode'] == 'refuse' for p in si),
            all_I_reviewed_refuse=sum(p['right_mode'] == 'refuse' for p in si),
            literal_single_atom_minimality_proved=0),
        AB_pairs=dict(total=len(ab), same_determinate_mode=sum(p['determinate'] and p['left_mode'] == p['right_mode'] for p in ab),
            unknown_pairs=sum(not p['determinate'] for p in ab), residual_detail_or_scope_caveats=len(caveats),
            no_specific_difference_identified=len(ab) - len(caveats), formal_equivalence_proved=0),
        old18_repairs=dict(total=len(repairs), statuses=dict(Counter(r['status'] for r in repairs))),
        background_slots=90, unique_background_documents=inventory['unique_background_documents'],
        history_exposed=True, independent_gold=False, approved_for_training=False,
        approved_semantic_labels=0, independent_semantic_coverage=0.0, minimum_independent_coverage=0.9,
        gpu_launch_ready=False, new_gpu_forwards=0, generated_answers=0, trained_probes=0,
        source_questions_backgrounds_partitions_and_slots_unchanged=True,
        quality_disposition='Exposed author QA completed; residual issues retained. Not unconditional semantic acceptance or proof of probe reliability.')
    risks = [
        dict(id='R01', issue='独立审核与上下文审计缺失', affected_ids=[r['id'] for r in rows],
            evidence='作者验收有AGENTS/历史及旧判断暴露；独立标签0，semantic coverage0，90%要求不变。',
            disposition='待实际独立审核，保持GPU关闭；用户暂无外部渠道，不重复索要或以新上下文冒充独立。'),
        dict(id='R02', issue='扑克have to义务范围未定', affected_ids=[r['id'] for r in rows if r['id'].startswith('stv17')],
            evidence='S/K四条为unknown；C两条描述性正反已对齐，暂判conflict，但没有证明完整义务规则。I无showdown/亮牌动作。',
            disposition='保留四unknown和C描述层说明；不改题、不新增材料，交后续真实审核解释。'),
        dict(id='R03', issue='A/B仍有附带命题或范围差异', affected_pairs=[p['contrast'] + ':' + p['original_id'] for p in caveats],
            evidence='13/120组有具体细节/范围注意点；107组仅为未识别具体差异，不能称全部命题等价。',
            disposition='保留逐项引文和差异，不自动改稿；未来不能把全部A/B称严格纯措辞对照。'),
        dict(id='R04', issue='I保留熟悉线索及语言/百科知识边界',
            affected_ids=[r['id'] for r in rows if r['condition'] == 'I' and r['id'][:5] in {'stv01','stv05','stv06','stv13','stv18','stv21','stv26','stv29'}],
            evidence='日期、chess-like、Pachisi、Colorado、Sunday总体背景、显著姓名或菜品描述可能使模型凭词义或外部知识补答案；缺证判断要求文档支持链。',
            disposition='按只给定证据作作者判断，词义边界项保留moderate；以后把有据支持与猜中熟悉答案分开。'),
        dict(id='R05', issue='关系投影不等于形式单原子最小编辑', affected_ids=[p['right_id'] for p in si],
            evidence='58组支持→不足暂可接受，2组S义务范围未知；60组均未证明逐字或形式单原子最小性。Ohio删除多条支持路径。',
            disposition='保留关系/事实清单与完整S/I引文；不能称已证明单一词或单原子因果操纵。'),
        dict(id='R06', issue='来源政策修订、来源/背景重叠及小样本限制',
            evidence='本批沿用54发布来源引用和11补充来源，背景有旧train暴露和跨分区重复；评估仅12底题。',
            disposition='保留原overlap/source-policy记录，不称发布原文原样、全文新颖、独立确认或高精度估计。'),
        dict(id='R07', issue='执行器仍绑定v4-r2且新3B GPU路径未实测',
            evidence='v5作者验收不能给旧study就绪批准；真实行为评分导入仍待对应新版本。',
            disposition='审核满足后另存v5运行实现/协议；冻结L28/最多1拟合/开发触发/评估锁，长期GPU交用户。'),
    ]
    return summary, cells, pairs, si, repairs, risks, inventory


DELIVERY_README = '''v5 author acceptance and delivery seal — 2026-10-21

The public/ directory contains the two original, byte-identical v5 anonymous ZIPs.
Give one reviewer only input-review-a.zip, and another only input-review-b.zip.
No external delivery has been performed by this command.
Do not give independent reviewers this README, the coordinator archive, AGENTS,
project records, author judgments, probe predictions, or the other reviewer's ratings.
The coordinator archive includes exposed author judgments and is for coordination only.

Author QA is complete with residual issues. This is not independent semantic approval.
Poker S/K remain unknown. Thirteen A/B pairs have detail/scope caveats. All formal
semantic labels remain null. Construction coverage is 100%, independent coverage 0%,
the 90% requirement is unchanged, and GPU launch remains false. No further material
changes are applied in this acceptance version; unresolved items are recorded.

When an actual review channel exists, preserve original ratings and complete received
contexts separately; audit independence before any explicit approval. Intake agreement
creates candidates only. The old study remains bound to v4-r2. Any future v5 study
requires a separate implementation/protocol after review, fixed L28, at most one fit,
development-only triggering and a sealed evaluation lock. Leave the380 held-out bases.

Verify this seal without changing any artifacts:
sh scripts/run_semantic_transfer_v5_acceptance.sh --stage verify
'''


def process(run=DEFAULT, write=False):
    preserved = read(PRESERVED)
    require(isinstance(preserved, dict) and len(preserved) >= 322, 'Preservation snapshot incomplete')
    for name, sha in preserved.items():
        require(digest(ROOT / name) == sha, f'Preserved source changed: {name}')
    rows, _, _, _, _ = intake.load_materials(MATERIALS)
    value = read(RATINGS)
    summary, cells, pairs, si, repairs, risks, inventory = derive(rows, value)
    require(len(pairs) == 300 and len(si) == 60 and len(repairs) == 18, 'Frozen audit denominators changed')
    material_gate = read(MATERIALS / 'review_gate.json')
    study = ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-preparation-v1'
    require(material_gate['gpu_launch_ready'] is False and read(study / 'review_gate.json')['gpu_launch_ready'] is False,
        'Original gates must remain closed')
    public = {}
    for side in ['a', 'b']:
        original = MATERIALS / f'handoff/input-review-{side}.zip'
        public[f'public/input-review-{side}.zip'] = original.read_bytes()
    source_paths = [RATINGS, PRESERVED, Path(__file__), ROOT / 'scripts/run_semantic_transfer_v5_acceptance.sh']
    protocol = dict(task='CPU_replay_exposed_author_acceptance_and_delivery_seal',
        material_protocol_sha256=digest(MATERIALS / 'protocol.json'),
        source_sha256={str(p.relative_to(ROOT)): digest(p) for p in source_paths},
        preserved_paths=len(preserved), independent_gold=False, approved_for_training=False,
        gpu_launch_ready=False, label_approval_or_inference_path=False,
        seal_meaning='Hash/version seal only; no OS permission change and no future research approval.')
    outputs = {'protocol.json': protocol, 'summary.json': summary, 'ratings.json': value,
        'cells.csv': csv_text(cells), 'pairs.csv': csv_text(pairs), 'S_to_I60.csv': csv_text(si),
        'old18_repairs.csv': csv_text(repairs), 'risks.json': risks, 'fulltext_inventory.json': inventory,
        'preserved_sources.json': preserved, 'README.txt': DELIVERY_README, **public}
    coordinator_members = {name: content for name, content in outputs.items() if not name.startswith('public/')}
    for relative in ['protocol.json','preflight.json','review_gate.json','coordinator/review_mapping.json',
            'reports/overlap_audit.json','coordinator/source_policy_amendment.json','coordinator/control_revision.json']:
        coordinator_members['material_snapshot/' + relative] = (MATERIALS / relative).read_bytes()
    coordinator_members['material_snapshot/inputs.json'] = (MATERIALS / 'materials/inputs.json').read_bytes()
    outputs['coordinator/v5-acceptance-coordinator.zip'] = archive(coordinator_members)
    checksums = {name: hashlib.sha256(bytes_for(content)).hexdigest() for name, content in sorted(outputs.items())}
    manifest = dict(status=summary['status'], files_sha256=checksums, public_delivery_already_sent=False,
        anonymous_zip_sources={name: str((MATERIALS / 'handoff' / Path(name).name).relative_to(ROOT)) for name in public},
        coordinator_contains_exposed_judgments=True, independent_labels=0, gpu_launch_ready=False,
        manifest_does_not_hash_itself=True)
    outputs['seal_manifest.json'] = manifest
    outputs['SHA256SUMS'] = ''.join(f'{sha}  {name}\n' for name, sha in checksums.items())
    for name, content in outputs.items():
        put(run / name, content, write)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['seal', 'verify'], default='verify')
    parser.add_argument('--run-dir', type=Path, default=DEFAULT)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    require(run.is_relative_to(ROOT / 'runs'), 'Output must stay in project runs')
    for path in [MATERIALS, PARENT, ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-preparation-v1']:
        require(not run.is_relative_to(path.resolve()) and not path.resolve().is_relative_to(run),
            'Keep acceptance separate from frozen material/study directories')
    print(serialize(process(run, write=args.stage == 'seal')))


if __name__ == '__main__':
    main()
