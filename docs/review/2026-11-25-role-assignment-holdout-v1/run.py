"""Run the fixed joint role assignment on a separately prepared holdout."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_role_assign as candidate

base = candidate.base
old_contract = base.contract
base.PACK = HERE
base.pick_per_rule = candidate.assign


def contract():
    sources = old_contract()
    for file in (Path(__file__), ROOT / 'scripts/query_determinacy_role_assign.py'):
        sources[str(file.relative_to(ROOT))] = base.local.hash_file(file)
    return sources


base.contract = contract
base.main()
