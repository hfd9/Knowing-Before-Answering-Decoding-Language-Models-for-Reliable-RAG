"""Authored source records and independent reference construction for the held-out CPU packet."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_delegation_paired as paired
from query_determinacy_delegation import context, solve


# A/B denote the semantic grantor/recipient, independent of their order in the text.
PATTERNS = {
    'handover_record': (
        ('移交清册显示，本件复核单的签发原由「{A}」负责，现交给「{B}」；这是清册里的唯一授权。',
         '若本件复核单的签发权限由「{A}」移交给「{B}」，{r}在本件停止适用，准入结论改为：{y}。'),
        ('对本件复核单，档案只承认一项权力移交：接手签发的是「{B}」，把权力交出去的是「{A}」。',
         '结论为{y}，同时以本条替代{r}，但仅限「{B}」接手「{A}」交出的本件复核单签发权限时。'),
    ),
    'signature_registry': (
        ('签署权限簿只有这一行：可代行本件复核单签发的是「{B}」，该权限由「{A}」授出。',
         '例外结论是{y}。本例外仅面向由「{A}」赋权、由「{B}」签发本件复核单的情形；遇此情形应以本条代替{r}。'),
        ('本件签署权限簿记载一项且仅一项代理关系。「{A}」是签发权的授出方，「{B}」是承接方。',
         '核对「{B}」的签发权是否源自「{A}」。若是，本件复核单适用本条而非{r}，并作{y}处理。'),
    ),
    'delegation_file': (
        ('本件唯一一项授权是「{A}」授权「{B}」签发复核单。',
         '除非本件的复核单签发已由「{A}」发出委托、并由「{B}」承接，否则不采用本例外；适用本例外时跳过{r}并作{y}处理。'),
        ('本件存档的复核单签发授权只有一份。受托签发栏填的是「{B}」，发出委托栏填的是「{A}」。',
         '本件若由「{A}」授权「{B}」签发复核单，则改按本条判为{y}，优先于{r}。'),
    ),
    'mandate_file': (
        ('本件复核单的核发权仅有一笔委托：「{B}」从「{A}」取得该权。',
         '本件若确有「{A}」交给「{B}」的核发权限凭单，就应舍弃{r}的默认判法，以本条作{y}结案。此处权限专指本件复核单。'),
        ('权限凭单只列本件复核单的一笔转授。「{B}」收下了核发权限，作出转授的单位是「{A}」。',
         '本条的生效条件是「{B}」取得「{A}」授予的本件复核单核发权。条件满足时，本件判为{y}，本条取代{r}。'),
    ),
}
# Each novel family has both conclusions and both world positions for the exception.
ROOT_SPECS = (
    ('C01', 'novel', 'handover_record', '档案接收', '扫描归档', '整档组', '调阅组', 'R1', False),
    ('C02', 'novel', 'handover_record', '票样封存', '骑缝复验', '留样组', '核印组', 'R2', False),
    ('C03', 'novel', 'signature_registry', '工料回收', '样品复核', '库验组', '单证组', 'R2', True),
    ('C04', 'novel', 'signature_registry', '版签存档', '原稿复验', '版签组', '存稿组', 'R1', True),
    ('M01', 'mixed', 'delegation_file', '清单归并', '凭单留存', '归并组', '留单组', 'R1', False),
    ('M02', 'mixed', 'mandate_file', '库存初核', '凭证终验', '库核组', '凭审组', 'R2', False),
)
ANSWER_WORD = {'Y': '准入', 'N': '不准入'}
DEFAULTS = {'R1': 'Y', 'R2': 'N'}


def sources(category1, category2, inverted):
    order = (category2, category1) if inverted else (category1, category2)
    return {'W1': f'本件类别为「{order[0]}」。', 'W2': f'本件类别为「{order[1]}」。',
            'R1': f'「{category1}」类别按本条判为准入。', 'R2': f'「{category2}」类别按本条判为不准入。'}


def reference_worlds(order, affected, outcome, applies):
    worlds = {}
    for world, base in zip(('W1', 'W2'), order, strict=True):
        if affected is None or (base == affected and applies is None):
            worlds[world] = {'applies': None, 'rule': None, 'answer': 'X', 'evidence': []}
            continue
        hit = base == affected
        used_exception = hit and applies
        worlds[world] = {'applies': bool(used_exception), 'rule': 'R3' if used_exception else base,
                         'answer': outcome if used_exception else DEFAULTS[base],
                         'evidence': [world, base, 'R3'] + (['F1'] if hit else [])}
    return worlds


def make():
    cases, refs = {}, {}
    for root, group, family, c1, c2, grantor, recipient, affected, inverted in ROOT_SPECS:
        outcome = 'N' if affected == 'R1' else 'Y'
        exception = {'grantor': grantor, 'recipient': recipient, 'overrides': affected, 'answer': outcome}
        order = ('R2', 'R1') if inverted else ('R1', 'R2')
        for wording, (fact, rule) in enumerate(PATTERNS[family], 1):
            for direction, matches in (('match', True), ('reverse', False)):
                key = f'{root}-{wording}-{direction}'
                a, b = (grantor, recipient) if matches else (recipient, grantor)
                cases[key] = sources(c1, c2, inverted) | {'F1': fact.format(A=a, B=b),
                              'R3': rule.format(A=grantor, B=recipient, r=affected, y=ANSWER_WORD[outcome])}
                worlds = reference_worlds(order, affected, outcome, matches)
                refs[key] = {'root': root, 'group': group, 'family': family, 'wording': wording, 'direction': direction,
                             'structure': {'exception': exception, 'grant': {'grantor': a, 'recipient': b}},
                             'result': {'worlds': worlds, 'final': outcome if matches else 'U'}}
    cases['X01'] = sources('盖签验收', '清册复检', False) | {
        'F1': '本件唯一一项签发授权的受权单位确定为「盖验组」。授权方登记页缺失，无法恢复。',
        'R3': '本件若由「审册组」授权「盖验组」签发复核单，则改按本条判为不准入，优先于R1。'}
    refs['X01'] = {'root': 'X01', 'group': 'boundary', 'family': 'missing_grantor',
                   'structure': {'grant': None, 'exception': {'grantor': '审册组', 'recipient': '盖验组',
                                                              'answer': 'N', 'overrides': 'R1'}},
                   'result': {'worlds': reference_worlds(('R1', 'R2'), 'R1', 'N', None), 'final': 'X'}}
    cases['X02'] = sources('印记审验', '凭单复存', True) | {
        'F1': '台账只登记一条授权，但两份等权副本方向相反：甲写「存凭组」给「验印组」，乙写「验印组」给「存凭组」。签发权限方向尚未核定。',
        'R3': '本件若由「存凭组」授权「验印组」签发复核单，则改按本条判为准入，优先于R2。'}
    refs['X02'] = {'root': 'X02', 'group': 'boundary', 'family': 'conflicting_grants',
                   'structure': {'grant': None, 'exception': {'grantor': '存凭组', 'recipient': '验印组',
                                                              'answer': 'Y', 'overrides': 'R2'}},
                   'result': {'worlds': reference_worlds(('R2', 'R1'), 'R2', 'Y', None), 'final': 'X'}}
    cases['X03'] = sources('函件托管', '封缄复验', True) | {
        'F1': '本件唯一一项授权是「托管组」授权「验封组」签发复核单。',
        'R3': '两份尚未核定的等权版本都以「托管组」授权「验封组」签发本件复核单为条件。一个版本取代R1并判为不准入，另一个版本取代R2并判为准入。'}
    refs['X03'] = {'root': 'X03', 'group': 'boundary', 'family': 'conflicting_rule_effects',
                   'structure': {'grant': {'grantor': '托管组', 'recipient': '验封组'}, 'exception': None},
                   'result': {'worlds': reference_worlds(('R2', 'R1'), None, None, None), 'final': 'X'}}
    return cases, refs


def verify(cases, refs):
    protocol = json.loads((HERE / 'protocol.json').read_text())
    assert cases.keys() == refs.keys()
    prior = [HERE.parent / '2026-11-23-delegation-new-wording-v1' / 'cases.json',
             *(HERE.parent / '2026-11-23-rule-applicability-paired-v1' / f'{part}-cases.json'
               for part in ('dev', 'heldout'))]
    old_rows = [row for file in prior for row in json.loads(file.read_text()).values()]
    for slot in ('W1', 'W2', 'R1', 'R2', 'R3', 'F1'):
        assert not {row[slot] for row in cases.values()} & {row[slot] for row in old_rows}, slot
    layout = {}
    for group, spec in protocol['groups'].items():
        selected = {key: ref for key, ref in refs.items() if ref['group'] == group}
        if group != 'boundary':
            paired.inspect_split({key: cases[key] for key in selected}, selected, spec['roots'])
            assert len({ref['family'] for ref in selected.values()}) == spec['families']
            for fam in {ref['family'] for ref in selected.values()}:
                labels = {ref['result']['final'] for ref in selected.values() if ref['family'] == fam}
                if group == 'novel':
                    assert labels == {'N', 'U', 'Y'}
        else:
            assert len(selected) == spec['cases']
            for key, ref in selected.items():
                context(cases[key])
                assert ref['result']['final'] == 'X' and solve(cases[key], ref['structure']) == ref['result']
        layout[group] = dict(Counter(ref['result']['final'] for ref in selected.values()))
    return layout


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--write', action='store_true')
    args = cli.parse_args()
    cases, refs = make()
    layout = verify(cases, refs)
    for name, content in (('cases.json', cases), ('author-reference.json', refs)):
        path = HERE / name
        if args.write:
            with path.open('x') as out:
                json.dump(content, out, ensure_ascii=False, sort_keys=True, indent=2)
                out.write('\n')
        else:
            assert json.loads(path.read_text()) == content
    print(layout)
