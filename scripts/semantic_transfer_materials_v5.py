"""CPU-only v5 relation-control repair. Author entailment ledgers do not approve labels."""

import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / 'prompts/semantic_transfer_control_revision_v1.json'
SPEC = ROOT / 'prompts/semantic_transfer_materials_v5.json'
PARENT = ROOT / 'prompts/semantic_transfer_materials_v4.json'
PARENT_RUN = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v4-r2'
SOURCES = ROOT / 'prompts/semantic_transfer_supplemental_sources_v1.json'
AMENDMENT = ROOT / 'prompts/semantic_transfer_source_augmentation_v1.json'
OLD_REVIEW = ROOT / 'docs/records/2026-10-20-semantic-transfer-author-input-review-ratings.json'
OLD_PROPOSALS = ROOT / 'docs/records/2026-10-20-semantic-transfer-author-input-review-revision-proposals.json'
DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v5'
SEEDS = dict(a=2026102051, b=2026102052)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def load_core():
    core = module('_semantic_transfer_v5_isolated_core', ROOT / 'scripts/semantic_transfer_materials.py')
    core.AUTHORED, core.DEFAULT = SPEC, DEFAULT
    original_assemble, original_prepare, original_put = core.assemble, core.prepare, core.put

    def validate_revision(spec):
        revision, parent = core.read(REVISION), core.read(PARENT)
        assert revision['parent_spec_sha256'] == core.digest(PARENT)
        assert revision['parent_protocol_sha256'] == core.digest(PARENT_RUN / 'protocol.json')
        assert revision['frozen_design_sha256'] == core.digest(core.DESIGN)
        assert revision['author_review_sha256'] == core.digest(OLD_REVIEW)
        assert revision['revision_proposals_sha256'] == core.digest(OLD_PROPOSALS)
        assert revision['independent_gold'] is False and revision['approved_labels'] == 0 and revision['gpu_launch_ready'] is False
        # Validate the unchanged source-augmentation policy on its original v4 batch.
        parent_module = module('_semantic_transfer_v5_parent_validation', ROOT / 'scripts/semantic_transfer_materials_v4.py')
        parent_module.load_core().validate_augmentation(parent)
        parent_protocol = core.read(PARENT_RUN / 'protocol.json')
        for relative, sha in {**parent_protocol['implementation_sha256'], **parent_protocol['source_sha256']}.items():
            assert core.digest(ROOT / relative) == sha, relative
        rows = core.read(PARENT_RUN / 'materials/inputs.json')
        assert core.digest(PARENT_RUN / 'materials/inputs.json') == parent_protocol['inputs_sha256']
        by_id = {r['id']: r for r in rows}
        expected = copy.deepcopy(parent)
        units = {u['original_id']: u for u in expected['units']}
        seen = set()
        for edit in revision['document_changes']:
            row = by_id[edit['id']]
            assert all(edit[k] == row[k] for k in ['original_id', 'partition', 'expression', 'condition'])
            assert row['target_slots'][edit['target_index']] == edit['doc_slot']
            key = (edit['id'], edit['doc_slot'])
            assert key not in seen
            seen.add(key)
            target = units[edit['original_id']]['expressions'][edit['expression']][edit['condition']]
            assert target[edit['target_index']] == edit['before'] == row['docs'][edit['doc_slot'] - 1]
            assert core.text_hash(edit['before']) == edit['before_sha256']
            assert core.text_hash(edit['after']) == edit['after_sha256']
            target[edit['target_index']] = edit['after']
        for edit in revision['unit_metadata_changes']:
            unit = units[edit['original_id']]
            assert unit[edit['field']] == edit['before']
            assert edit['field'] in ['missing_premise', 'conflict_explanation']
            unit[edit['field']] = edit['after']
        for key, change in revision['top_level_changes'].items():
            assert parent.get(key) == change['before']
            expected[key] = change['after']
        assert spec == expected, 'Unlisted change outside versioned repair'
        changed_I = {by_id[e['id']]['original_id'] for e in revision['document_changes'] if e['condition'] == 'I'}
        assert len(changed_I) == 27 and changed_I == set(revision['I_reconstruction'])
        assert set(revision['unchanged_I_bases']) == {u['original_id'] for u in spec['units']} - changed_I
        for old, new in zip(parent['units'], spec['units']):
            assert old['question'] == new['question'] and old['source_citations'] == new['source_citations']
            assert old.get('supplemental_source_citations') == new.get('supplemental_source_citations')
        return revision

    def revised_assemble(design, spec, selected, partition, catalog):
        revision = validate_revision(spec)
        result = original_assemble(design, spec, selected, partition, catalog)
        rows = result[0]
        assert len(rows) == 240 and not result[1]
        parent_rows = {r['id']: r for r in core.read(PARENT_RUN / 'materials/inputs.json')}
        ledger = []
        by_base = {u['original_id']: u for u in spec['units']}
        unchanged_facts = {
            'train_1179': ['Luoding is a county-level city', 'Dingzhou is in Hebei in northern China'],
            'train_1605': ['US forces participated in Korean War combat campaigns', 'An armistice established a cease-fire'],
            'train_25': ['CNN reported in2014', 'FBI and other law-enforcement trainees visited a DC museum', 'The lesson concerned civil-liberties horrors']}
        for row in rows:
            old = parent_rows[row['id']]
            assert all(row[k] == old[k] for k in ['id', 'original_id', 'partition', 'expression', 'condition', 'question', 'target_slots'])
            assert all(row['docs'][s-1] == old['docs'][s-1] for s in range(1, 6) if s not in row['target_slots'])
            if row['condition'] != 'I':
                continue
            unit = by_base[row['original_id']]
            support = unit['expressions'][row['expression']]['S']
            residual = unit['expressions'][row['expression']]['I']
            # Reject new numeric values; this does NOT prove semantic entailment.
            assert set(re.findall(r'\d+', ' '.join(residual))) <= set(re.findall(r'\d+', ' '.join(support)))
            declaration = revision['I_reconstruction'].get(row['original_id'])
            if declaration:
                assert residual == declaration[row['expression']]
                retained = declaration['retained_non_answer_facts']
                note = declaration['entailment_note']
                removed = declaration['removed_required_relation']
            else:
                retained = unchanged_facts[row['original_id']]
                note = 'Previously reviewed relation-level residual; unchanged from v4-r2, still not independently approved.'
                removed = unit['missing_premise']
            ledger.append(dict(id=row['id'], original_id=row['original_id'], partition=row['partition'],
                expression=row['expression'], fixed_question=row['question'], target_slots=row['target_slots'], removed_required_relation=removed,
                author_retained_fact_inventory=retained, matched_S_passages=support, residual_I_passages=residual,
                author_entailment_note=note, numeric_subset_check=True, independent_entailment_verified=False,
                literal_or_formal_single_atom_minimality_proved=False))
        previous = core.read(OLD_REVIEW)
        old_caveats = []
        revised_by_id = {r['id']: r for r in rows}
        for oid, note in previous['base_decisions'].items():
            for condition, reason in note.get('expression_caveats', {}).items():
                pair = [r for r in rows if r['original_id'] == oid and r['condition'] == condition]
                assert len(pair) == 2 and any(r['docs'] != parent_rows[r['id']]['docs'] for r in pair)
                old_caveats.append(dict(original_id=oid, condition=condition, previous_caveat=reason,
                    revised_ids=[r['id'] for r in pair], disposition='repair_authored_pending_fresh_semantic_review'))
        assert len(old_caveats) == 18 and len(ledger) == 60
        core.revision_audit = dict(constructed_cells=240, same_question_and_background_cells=240,
            changed_cells=sum(r['docs'] != parent_rows[r['id']]['docs'] for r in rows),
            unchanged_cells=sum(r['docs'] == parent_rows[r['id']]['docs'] for r in rows),
            changed_target_passages=len(revision['document_changes']), repaired_I_cells=54,
            unchanged_I_cells=6, I_relation_ledgers=ledger, previous_AB_caveats=old_caveats,
            residual_review_risks=revision['residual_review_risks'],
            independent_semantic_labels=0, gpu_launch_ready=False,
            limitation='Numeric/hash/slot checks and an exposed author fact inventory do not prove semantic entailment, exact A/B equivalence or literal one-premise minimality.')
        return result

    def fresh_packets(rows):
        packets, mapping = {}, {}
        for side, seed in SEEDS.items():
            order = list(rows)
            random.Random(seed).shuffle(order)
            items = []
            for n, row in enumerate(order, 1):
                ticket = f'R{n:03d}'
                items.append(dict(item_id=ticket, question=row['question'], documents=row['docs']))
                mapping.setdefault(row['id'], {})[side] = ticket
            packets[side] = dict(task='input_evidence_semantics_review', items=items)
        return packets, mapping

    def versioned_put(path, value, write):
        value = copy.deepcopy(value)
        if path.name == 'overlap_audit.json':
            value['shared_backgrounds_across_partitions'].sort(key=lambda r: r['doc_id'])
        if path.name == 'preflight.json':
            value['source_augmented_author_materials'] = True
            value['construction_coverage_requirement_met'] = value['construction_coverage'] >= .90
            value['coverage_note'] = 'All240 authored inputs constructed; independent semantic coverage remains0. Author relation-level projection audit is not semantic approval or proof of literal minimality.'
        if path.name == 'protocol.json':
            revision = validate_revision(core.read(SPEC))
            for name, content in [('sources/supplemental_source_excerpts.json', core.read(SOURCES)),
                    ('coordinator/source_policy_amendment.json', core.read(AMENDMENT)),
                    ('coordinator/control_revision.json', revision),
                    ('reports/relation_control_audit.json', core.revision_audit)]:
                original_put(path.parent / name, content, write)
            value.update(material_version=5, source_augmented_author_materials=True,
                parent_material_protocol_sha256=core.digest(PARENT_RUN / 'protocol.json'),
                control_revision_sha256=core.digest(REVISION), supplemental_sources_sha256=core.digest(SOURCES),
                source_policy_amendment_sha256=core.digest(AMENDMENT), review_packet_shuffle_seeds=SEEDS,
                semantic_quality_status='author_repaired_pending_independent_review_not_proved_equivalent')
            value['implementation_sha256'].update(core.read(PARENT_RUN / 'protocol.json')['implementation_sha256'])
            value['implementation_sha256'].update({str(p.relative_to(ROOT)): core.digest(p)
                for p in [Path(__file__), ROOT / 'scripts/run_semantic_transfer_materials_v5.sh']})
            value['source_sha256'].update({str(p.relative_to(ROOT)): core.digest(p)
                for p in [REVISION, PARENT, PARENT_RUN / 'protocol.json', PARENT_RUN / 'materials/inputs.json',
                    SOURCES, AMENDMENT, OLD_REVIEW, OLD_PROPOSALS]})
        if path.name == 'review_gate.json':
            value.update(status='blocked_pending_independent_review_of_repaired_v5',
                construction_coverage_requirement_met=True,
                reasons=['No two auditable history-independent input reviews available.',
                    'All240 semantic labels remain null; exposed author repairs do not approve labels.',
                    'Relation-level projection and A/B fact inventories require semantic review; residual risks are recorded.'])
        return original_put(path, value, write)

    def handoff(base, write):
        entries = {}
        for side in ['a', 'b']:
            contents = {name: (base / f'review_{side}' / name).read_bytes()
                for name in ['packet.json', 'rubric.json', 'ratings_template.json', 'review.html']}
            contents['README.txt'] = ('Read the question and every supplied document. Use only supplied evidence. '
                'Do not receive project history, author labels, other ratings, model answers or probe outputs. '
                'Record the complete context actually received and disclose exposure. Keep unknown judgments. '
                'Fill a copy of ratings_template.json; preserve packet_sha256.\n').encode()
            contents['checksums.json'] = core.json_text({k: hashlib.sha256(v).hexdigest() for k, v in contents.items()}).encode()
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for name in sorted(contents):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    archive.writestr(info, contents[name])
            data = buffer.getvalue()
            path = base / f'handoff/input-review-{side}.zip'
            if path.exists():
                assert path.read_bytes() == data, 'Handoff ZIP changed'
            elif write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            else:
                raise ValueError(f'Missing handoff ZIP: {path}')
            entries[side] = dict(file=path.name, sha256=hashlib.sha256(data).hexdigest(),
                members={k: hashlib.sha256(v).hexdigest() for k, v in contents.items()})
        original_put(base / 'handoff/manifest.json', entries, write)

    def prepare(base, write=True):
        base = Path(base).resolve()
        assert not base.is_relative_to(PARENT_RUN) and not PARENT_RUN.is_relative_to(base)
        result = original_prepare(base, write)
        handoff(base, write)
        result.update(material_version=5, changed_cells=core.revision_audit['changed_cells'],
            unchanged_cells=core.revision_audit['unchanged_cells'], changed_target_passages=core.revision_audit['changed_target_passages'],
            repaired_I_cells=54, independently_approved_labels=0, semantic_entailment_proved=False)
        return result

    core.assemble, core.put, core.make_review_packets, core.prepare = revised_assemble, versioned_put, fresh_packets, prepare
    core.validate_revision = validate_revision
    return core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify'], default='prepare')
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    args = parser.parse_args()
    base = args.run_dir.resolve()
    assert base.is_relative_to(ROOT / 'runs') and base.name.startswith('qwen2.5-3b-semantic-transfer-materials-v5')
    if args.stage == 'prepare':
        base.mkdir(parents=True, exist_ok=True)
    core = load_core()
    print(core.json_text(core.prepare(base, write=args.stage == 'prepare')))


if __name__ == '__main__':
    main()
