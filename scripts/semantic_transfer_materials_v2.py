"""Versioned author-audit repair; reuse the unchanged v1 CPU builder in an isolated module."""

import copy
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load_core():
    specification=importlib.util.spec_from_file_location('_semantic_transfer_material_core_v2',ROOT/'scripts/semantic_transfer_materials.py')
    core=importlib.util.module_from_spec(specification)
    specification.loader.exec_module(core)
    core.AUTHORED=ROOT/'prompts/semantic_transfer_materials_v2.json'
    core.DEFAULT=ROOT/'runs/qwen2.5-3b-semantic-transfer-materials-v2'
    original_put=core.put

    def versioned_put(path,value,write):
        if path.name=='protocol.json':
            value=copy.deepcopy(value)
            value['material_version']=2
            value['implementation_sha256'].update({str(p.relative_to(ROOT)):core.digest(p) for p in
                [Path(__file__),ROOT/'scripts/run_semantic_transfer_materials_v2.sh']})
        return original_put(path,value,write)

    core.put=versioned_put
    return core


if __name__=='__main__':load_core().main()
