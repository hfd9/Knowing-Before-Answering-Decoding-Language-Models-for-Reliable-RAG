"""Versioned replay repair: stable overlap-list order across independent processes."""

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_core():
    specification = importlib.util.spec_from_file_location(
        '_semantic_transfer_material_v4_replay_parent', ROOT / 'scripts/semantic_transfer_materials_v4.py')
    parent = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(parent)
    core = parent.load_core()
    core.DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v4-r2'
    original_put = core.put

    def stable_put(path, value, write):
        if path.name == 'overlap_audit.json':
            value = copy.deepcopy(value)
            value['shared_backgrounds_across_partitions'] = sorted(
                value['shared_backgrounds_across_partitions'], key=lambda row: row['doc_id'])
        if path.name == 'protocol.json':
            value = copy.deepcopy(value)
            value['material_replay_revision'] = 2
            value['replay_repair'] = 'Sort overlap audit list by document ID; all240 model inputs unchanged.'
            value['implementation_sha256'].update({str(p.relative_to(ROOT)): core.digest(p)
                for p in [Path(__file__), ROOT / 'scripts/run_semantic_transfer_materials_v4_replay.sh']})
        return original_put(path, value, write)

    core.put = stable_put
    return core


if __name__ == '__main__':
    load_core().main()
