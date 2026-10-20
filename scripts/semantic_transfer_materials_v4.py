"""CPU-only, explicitly source-augmented author materials; old source-only runs stay frozen."""

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'prompts/semantic_transfer_supplemental_sources_v1.json'
AMENDMENT = ROOT / 'prompts/semantic_transfer_source_augmentation_v1.json'
PARENT_SPEC = ROOT / 'prompts/semantic_transfer_materials_v3.json'


def load_core():
    specification = importlib.util.spec_from_file_location(
        '_semantic_transfer_material_core_v4', ROOT / 'scripts/semantic_transfer_materials.py')
    core = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(core)
    core.AUTHORED = ROOT / 'prompts/semantic_transfer_materials_v4.json'
    core.DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v4'
    original_put, original_assemble = core.put, core.assemble

    def validate_augmentation(spec):
        amendment = core.read(AMENDMENT)
        sources = core.read(SOURCES)
        parent = core.read(PARENT_SPEC)
        assert amendment['parent_material_spec_sha256'] == core.digest(PARENT_SPEC)
        assert amendment['frozen_design_sha256'] == core.digest(core.DESIGN)
        assert amendment['supplemental_sources_sha256'] == core.digest(SOURCES)
        changed = {a['original_id'] for a, b in zip(spec['units'], parent['units']) if a != b}
        formerly_missing = {u['original_id'] for u in parent['units'] if u['expressions'] is None}
        assert changed == formerly_missing == {u['original_id'] for u in amendment['changes']}
        assert len(changed) == 8
        assert [u['original_id'] for u in spec['units']] == [u['original_id'] for u in parent['units']]
        lookup = {s['source_id']: s for s in sources['sources']}
        assert len(lookup) == len(sources['sources']) == 11
        for source in lookup.values():
            assert core.text_hash(source['excerpt']) == source['excerpt_sha256']
            assert source['url'].startswith('https://') and source['publisher'] and source['locator']
            assert len(source['excerpt'].split()) <= (10 if source['source_id'] in {'X002', 'X006'} else 25)
        used = set()
        for unit in spec['units']:
            assert unit['expressions'] is not None and unit['independent_gold'] is False
            if unit['original_id'] not in changed:
                continue
            citations = unit['supplemental_source_citations']
            assert citations
            for cite in citations:
                source = lookup[cite['source_id']]
                assert cite['excerpt_sha256'] == source['excerpt_sha256']
                assert source['excerpt'][cite['start']:cite['end']] == cite['quote']
                used.add(cite['source_id'])
        assert used == set(lookup)
        assert amendment['constructed_after'] == 240
        assert amendment['independently_reviewed_semantic_labels'] == 0
        assert amendment['gpu_launch_ready'] is False
        return sources, amendment

    def augmented_assemble(design, spec, selected, partition, catalog):
        validate_augmentation(spec)
        result = original_assemble(design, spec, selected, partition, catalog)
        assert len(result[0]) == 240 and not result[1]
        return result

    def versioned_put(path, value, write):
        if path.name == 'preflight.json':
            value = copy.deepcopy(value)
            value['source_augmented_author_materials'] = True
            value['construction_coverage_requirement_met'] = value['construction_coverage'] >= 0.90
            value['coverage_note'] = ('Construction coverage is100%, not independent semantic-label coverage. '
                'All240 semantic labels remain null; independent coverage is0. Source-only predecessor results are preserved separately.')
        if path.name == 'protocol.json':
            sources, amendment = validate_augmentation(core.read(core.AUTHORED))
            original_put(path.parent / 'sources/supplemental_source_excerpts.json', sources, write)
            original_put(path.parent / 'coordinator/source_policy_amendment.json', amendment, write)
            value = copy.deepcopy(value)
            value.update(material_version=4, source_augmented_author_materials=True,
                source_policy_amendment_sha256=core.digest(AMENDMENT),
                supplemental_sources_sha256=core.digest(SOURCES), parent_material_spec_sha256=core.digest(PARENT_SPEC))
            value['implementation_sha256'].update({str(p.relative_to(ROOT)): core.digest(p)
                for p in [Path(__file__), ROOT / 'scripts/run_semantic_transfer_materials_v4.sh']})
            value['source_sha256'].update({str(p.relative_to(ROOT)): core.digest(p)
                for p in [SOURCES, AMENDMENT, PARENT_SPEC]})
        if path.name == 'review_gate.json':
            value = copy.deepcopy(value)
            value['status'] = 'blocked_pending_history_blind_semantic_reviews'
            value['construction_coverage_requirement_met'] = value['construction_coverage'] >= 0.90
            value['reasons'] = ['No two history-independent input reviews available.',
                'Independent semantic labels are0; author construction is not semantic approval.']
            assert value['construction_coverage'] == 1.0
            assert value['minimum_frozen_semantic_coverage'] == 0.90 and value['gpu_launch_ready'] is False
        return original_put(path, value, write)

    core.assemble = augmented_assemble
    core.put = versioned_put
    core.validate_augmentation = validate_augmentation
    return core


if __name__ == '__main__':
    load_core().main()
