"""Post-hoc CPU analysis of sealed v5 signal/behavior pairs; no new labels or fits."""

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path

import numpy as np

import semantic_transfer_exploratory_behavior_review as review

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'docs/records/2026-10-21-semantic-transfer-paired-analysis'
SPEC = 'prompts/semantic_transfer_paired_analysis_v1.json'
MODES = ['answer', 'refuse', 'conflict']
FIELDS = review.BEHAVIOR_FIELDS
CONTRASTS = ['S_to_I', 'S_to_C', 'S_to_K']


def bounds(value):
    review.require(value in {'yes', 'no', 'unknown'}, 'Invalid ternary behavior')
    return (1., 1.) if value == 'yes' else (0., 0.) if value == 'no' else (0., 1.)


def conjunction(*values):
    return 'no' if 'no' in values else 'unknown' if 'unknown' in values else 'yes'


def behavior(row, field):
    if field != 'erroneous_refusal':
        return row[field]
    answer = row['has_substantive_answer']
    return conjunction(row['acknowledges_insufficiency'],
        'no' if answer == 'yes' else 'yes' if answer == 'no' else 'unknown')


def make_pairs(rows):
    review.require(len(rows) == 240 and len({r['id'] for r in rows}) == 240,
        'Expected 240 unique source rows')
    groups = {}
    for r in rows:
        key = r['original_id']
        slot = r['expression'], r['condition']
        review.require(slot not in groups.setdefault(key, {}), 'Duplicate base/expression/condition')
        groups[key][slot] = r
        probs = r['probe_probabilities']
        review.require(set(probs) == set(MODES) and all(np.isfinite(v) and 0 <= v <= 1
            for v in probs.values()) and abs(sum(probs.values()) - 1) < 1e-10,
            'Invalid saved probabilities')
    review.require(len(groups) == 30, 'Expected 30 base questions')
    pairs = []
    for oid, g in sorted(groups.items()):
        review.require(set(g) == {(e, c) for e in ['A', 'B'] for c in ['S', 'K', 'I', 'C']},
            'Incomplete eight-variant base')
        for e in ['A', 'B']:
            left = g[e, 'S']
            for c in ['I', 'C', 'K']:
                right = g[e, c]
                review.require(left['question'] == right['question']
                    and left['partition'] == right['partition'], 'Cross-question/partition pair')
                expected = dict(I='refuse', C='conflict', K='answer')[c]
                eligible = left['exposed_author_input_mode'] == 'answer' and right[
                    'exposed_author_input_mode'] == expected
                pair = dict(original_id=oid, base_id=left['id'].split('_')[0],
                    question=left['question'], partition=left['partition'], expression=e,
                    contrast='S_to_' + c, left_id=left['id'], right_id=right['id'],
                    left_item_id=left['item_id'], right_item_id=right['item_id'],
                    left_author_mode=left['exposed_author_input_mode'],
                    right_author_mode=right['exposed_author_input_mode'],
                    author_reference_eligible=eligible,
                    left_probe=left['probe_pred'], right_probe=right['probe_pred'])
                for mode in MODES:
                    pair['left_p_' + mode] = left['probe_probabilities'][mode]
                    pair['right_p_' + mode] = right['probe_probabilities'][mode]
                    pair['delta_p_' + mode] = pair['right_p_' + mode] - pair['left_p_' + mode]
                for f in FIELDS + ['erroneous_refusal']:
                    pair['left_' + f], pair['right_' + f] = behavior(left, f), behavior(right, f)
                pairs.append(pair)
    review.require(len(pairs) == 180, 'Expected 180 constructed pairs')
    return pairs


def interval_metrics(pair, endpoint):
    focal = endpoint['focal_probability']
    field = endpoint['target_behavior']
    increase = pair['delta_p_' + focal] > 0
    metrics = {'delta_p_' + m: (pair['delta_p_' + m],) * 2 for m in MODES}
    metrics.update(focal_increase=(float(increase),) * 2,
        class_change=(float(pair['left_probe'] != pair['right_probe']),) * 2,
        target_behavior=bounds(pair['right_' + field]),
        increase_and_target_behavior=bounds(conjunction('yes' if increase else 'no', pair['right_' + field])),
        source_answer_and_target_answer=bounds(conjunction(pair['left_has_substantive_answer'],
            pair['right_has_substantive_answer'])),
        source_grounded_and_target_behavior=bounds(conjunction(pair['left_answer_grounded_correct'],
            pair['right_' + field])))
    for f in endpoint['behavior_changes']:
        a, b = bounds(pair['left_' + f]), bounds(pair['right_' + f])
        metrics['change_' + f] = b[0] - a[1], b[1] - a[0]
    return metrics


def cluster_summary(rows, endpoint, repeats=10000, seed=42):
    """Sample complete base groups with multiplicity; never resample variants alone."""
    review.require(bool(rows), 'Cannot summarize empty pair slice')
    bases = sorted({r['original_id'] for r in rows})
    metrics = [interval_metrics(r, endpoint) for r in rows]
    names = list(metrics[0])
    matrix = np.asarray([[metrics[i][k] for k in names] for i in range(len(rows))])
    totals = []
    for oid in bases:
        index = [i for i, r in enumerate(rows) if r['original_id'] == oid]
        totals.append(np.r_[len(index), matrix[index].sum(axis=0).ravel()])
    totals = np.asarray(totals)
    draws = np.random.default_rng(seed).integers(0, len(bases), (repeats, len(bases)))
    sampled = totals[draws].sum(axis=1)
    sample_means = (sampled[:, 1:] / sampled[:, :1]).reshape(repeats, len(names), 2)
    observed = matrix.mean(axis=0)
    result = dict(pairs=len(rows), bases=len(bases), resamples=repeats, seed=seed,
        unit='base_question_all_available_expressions_together', metrics={})
    for i, name in enumerate(names):
        lower, upper = map(float, observed[i])
        unknown = int(np.count_nonzero(matrix[:, i, 0] != matrix[:, i, 1]))
        result['metrics'][name] = dict(point=lower if not unknown else None,
            identification_lower=lower, identification_upper=upper,
            ambiguous_pairs=unknown,
            sampling_95_for_lower_bound=np.quantile(sample_means[:, i, 0], [.025, .975]).tolist(),
            sampling_95_for_upper_bound=np.quantile(sample_means[:, i, 1], [.025, .975]).tolist())
    focal = endpoint['focal_probability']
    outcome = endpoint['target_behavior']
    result['focal_sign_counts'] = dict(increase=sum(r['delta_p_' + focal] > 0 for r in rows),
        decrease=sum(r['delta_p_' + focal] < 0 for r in rows),
        equal=sum(r['delta_p_' + focal] == 0 for r in rows))
    result['class_transitions'] = {a: {b: sum(r['left_probe'] == a and r['right_probe'] == b
        for r in rows) for b in MODES} for a in MODES}
    result['target_behavior_counts'] = {v: sum(r['right_' + outcome] == v for r in rows)
        for v in ['yes', 'no', 'unknown']}
    result['increase_and_target_behavior_counts'] = {v: sum(conjunction(
        'yes' if r['delta_p_' + focal] > 0 else 'no', r['right_' + outcome]) == v
        for r in rows) for v in ['yes', 'no', 'unknown']}
    result['focal_by_target_behavior'] = {}
    for value in ['yes', 'no', 'unknown']:
        subset = [r for r in rows if r['right_' + outcome] == value]
        result['focal_by_target_behavior'][value] = dict(pairs=len(subset),
            bases=len({r['original_id'] for r in subset}),
            mean_delta=float(np.mean([r['delta_p_' + focal] for r in subset])) if subset else None,
            increase=sum(r['delta_p_' + focal] > 0 for r in subset))
    return result


def base_rows(rows, pairs):
    result = []
    for oid in sorted({r['original_id'] for r in rows}):
        cells = [r for r in rows if r['original_id'] == oid]
        g = {(r['expression'], r['condition']): r for r in cells}
        r = cells[0]
        counts = Counter(c['probe_pred'] for c in cells)
        i_rows = [g[e, 'I'] for e in ['A', 'B']]
        nref = sum(x['probe_pred'] == 'refuse' for x in i_rows)
        item = dict(base_id=r['id'].split('_')[0], original_id=oid, partition=r['partition'],
            question=r['question'], stable_probe_class=next(iter(counts)) if len(counts) == 1 else '',
            probe_answer=count(counts, 'answer'), probe_refuse=count(counts, 'refuse'),
            probe_conflict=count(counts, 'conflict'),
            SK_probe_conflict=sum(g[e, c]['probe_pred'] == 'conflict'
                for e in ['A', 'B'] for c in ['S', 'K']),
            I_probe_group={0: 'neither_refuse', 1: 'mixed', 2: 'both_refuse'}[nref],
            I_substantive_yes=sum(x['has_substantive_answer'] == 'yes' for x in i_rows))
        for e in ['A', 'B']:
            for c in ['S', 'K', 'I', 'C']:
                cell = g[e, c]
                item[e + '_' + c + '_probe'] = cell['probe_pred']
                item[e + '_' + c + '_substantive'] = cell['has_substantive_answer']
            for contrast in CONTRASTS:
                p = next(p for p in pairs if p['original_id'] == oid
                    and p['expression'] == e and p['contrast'] == contrast)
                focal = 'refuse' if contrast == 'S_to_I' else 'conflict'
                field = dict(S_to_I='has_substantive_answer', S_to_C='selection_without_resolution',
                    S_to_K='erroneous_refusal')[contrast]
                item[e + '_' + contrast + '_delta_' + focal] = p['delta_p_' + focal]
                item[e + '_' + contrast + '_target_behavior'] = p['right_' + field]
        result.append(item)
    return sorted(result, key=lambda r: r['base_id'])


def count(counts, key):
    return counts.get(key, 0)


def composition(rows, bases):
    i_rows = [r for r in rows if r['condition'] == 'I']
    groups = {}
    for name in ['both_refuse', 'mixed', 'neither_refuse']:
        selected = [b for b in bases if b['I_probe_group'] == name]
        ids = {b['original_id'] for b in selected}
        subset = [r for r in i_rows if r['original_id'] in ids]
        groups[name] = dict(bases=len(ids), original_ids=sorted(ids),
            base_ids=[b['base_id'] for b in selected], rows=len(subset),
            substantive=review.rate(subset, 'has_substantive_answer'),
            by_probe={probe: review.rate([r for r in subset if r['probe_pred'] == probe],
                'has_substantive_answer') for probe in MODES})
    matched = []
    for base in [b for b in bases if b['I_probe_group'] == 'mixed']:
        subset = [r for r in i_rows if r['original_id'] == base['original_id']]
        ref = next(r for r in subset if r['probe_pred'] == 'refuse')
        other = next(r for r in subset if r['probe_pred'] != 'refuse')
        a, b = bounds(ref['has_substantive_answer']), bounds(other['has_substantive_answer'])
        matched.append(dict(base_id=base['base_id'], original_id=base['original_id'],
            refuse_id=ref['id'], other_id=other['id'], refuse_answer=ref['has_substantive_answer'],
            other_answer=other['has_substantive_answer'],
            refuse_minus_other_lower=a[0] - b[1], refuse_minus_other_upper=a[1] - b[0]))
    return dict(I_probe_base_groups=groups, within_base_mixed_comparisons=matched,
        stable_eight_variant_classes=dict(Counter(b['stable_probe_class'] or 'varies' for b in bases)),
        SK_conflict_counts_per_base=dict(sorted(Counter(b['SK_probe_conflict'] for b in bases).items())),
        limitations='Mixed bases compare different expressions, not randomized probe assignments. '
        'These composition counts cannot identify a causal probe effect or a topic-adjusted population effect.')


def build(root=ROOT):
    spec = review.read(root, SPEC)
    review.require(spec['history_exposed'] is True and spec['independent_gold'] is False
        and spec['new_probe_fits'] == spec['new_gpu_calls'] == 0, 'Wrong analysis scope')
    review.verify_files(root, review.read(root, PREFIX + '-preserved.json'))
    review.verify_files(root, review.read(root, review.PREFIX + '-delivery-hashes.json'))
    packet, ratings, _ = review.load_sealed(root)
    rows = review.join_rows(root, packet, ratings)
    pairs = make_pairs(rows)
    review.require(sum(p['author_reference_eligible'] for p in pairs) == 174,
        'Reference membership mismatch; do not silently drop unknowns')
    predictions = {r['id']: r for r in review.read(root, review.RUN + '/predictions.json')['records']}
    for p in pairs:
        p['input_token_delta'] = predictions[p['right_id']]['input_tokens'] - predictions[
            p['left_id']]['input_tokens']
    bases = base_rows(rows, pairs)
    report = dict(schema_version=1, status='posthoc_paired_analysis_complete',
        history_exposed=True, independent_gold=False, formal_labels_added=0,
        new_gpu_calls=0, new_probe_fits=0, constructed_pairs=180,
        author_reference_eligible_pairs=174, author_reference_ineligible_pairs=6,
        bases=30, cells=240, bootstrap_repeats=spec['statistics']['bootstrap_repeats'],
        bootstrap_seed=spec['statistics']['bootstrap_seed'],
        interpretation=spec['boundaries'] + [spec['statistics']['bootstrap_interval']],
        source_hashes={p: review.digest((root / p).read_bytes()) for p in [SPEC,
            PREFIX + '-preserved.json', review.PREFIX + '-delivery-hashes.json',
            'scripts/semantic_transfer_paired_analysis.py']},
        contrasts={}, composition=composition(rows, bases))
    for name in CONTRASTS:
        group = [p for p in pairs if p['contrast'] == name]
        slices = dict(all_constructed=group,
            author_reference_eligible=[p for p in group if p['author_reference_eligible']],
            expression_A=[p for p in group if p['expression'] == 'A'],
            expression_B=[p for p in group if p['expression'] == 'B'])
        slices.update({partition: [p for p in group if p['partition'] == partition]
            for partition in ['semantic_train', 'semantic_dev', 'semantic_eval']})
        report['contrasts'][name] = {key: cluster_summary(value, spec['endpoints'][name],
            spec['statistics']['bootstrap_repeats'], spec['statistics']['bootstrap_seed'])
            for key, value in slices.items()}
    return report, pairs, bases, rows


def csv_bytes(rows):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def plots(root, report, pairs, bases, rows, stage):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False,
        'axes.spines.right': False, 'pdf.fonttype': 42, 'svg.hashsalt': 'kba-paired-v1'})
    base_ids = [r['original_id'] for r in bases]
    colors = dict(yes='#c65d21', no='#287ca3', unknown='#8a8a8a')
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 10), sharey=True)
    titles = ['S to I: P(refuse)', 'S to C: P(conflict)', 'S to K: P(conflict)']
    outcomes = ['Substantive answer at I', 'Unresolved selection at C', 'Insufficiency refusal at K']
    for ax, contrast, title, outcome in zip(axes, CONTRASTS, titles, outcomes):
        focal = 'refuse' if contrast == 'S_to_I' else 'conflict'
        field = dict(S_to_I='has_substantive_answer', S_to_C='selection_without_resolution',
            S_to_K='erroneous_refusal')[contrast]
        for p in [p for p in pairs if p['contrast'] == contrast]:
            y = base_ids.index(p['original_id']) + (0.15 if p['expression'] == 'B' else -0.15)
            ax.scatter(100 * p['delta_p_' + focal], y, s=27,
                marker='^' if p['expression'] == 'B' else 'o',
                color=colors[p['right_' + field]], edgecolors='white', linewidths=.3)
        metric = report['contrasts'][contrast]['all_constructed']['metrics']['delta_p_' + focal]
        lo, hi = metric['sampling_95_for_lower_bound']
        ax.errorbar(100 * metric['point'], 31, xerr=[[100 * (metric['point'] - lo)],
            [100 * (hi - metric['point'])]], fmt='D', color='#222222', capsize=4)
        ax.axvline(0, color='#555555', linewidth=.8)
        ax.axhline(30, color='#aaaaaa', linewidth=.6)
        ax.grid(axis='y', color='#eeeeee', linewidth=.5)
        ax.set_title(title + '\n' + outcome, fontsize=10)
        ax.set_xlabel('Probability change (percentage points)')
    axes[0].set_yticks(list(range(30)) + [31], [r['base_id'] for r in bases] + ['Mean + 95%'])
    axes[0].set_ylim(32, -1)
    axes[0].set_ylabel('Base question (A/B retained together in resampling)')
    from matplotlib.lines import Line2D
    legend = [Line2D([], [], marker='o', linestyle='', color=colors[v], label='Target behavior: ' + v)
        for v in ['yes', 'no', 'unknown']]
    legend += [Line2D([], [], marker=m, linestyle='', color='#333333', label='Expression ' + e)
        for e, m in [('A', 'o'), ('B', '^')]]
    fig.legend(handles=legend, loc='lower center', ncol=5, frameon=False)
    fig.suptitle('Existing v5 answers: paired signal change and target behavior\n'
        '30 bases / 60 pairs per contrast; exposed-author exploratory review', fontsize=12)
    fig.tight_layout(rect=(0, .045, 1, .94))
    figures = [(fig, '-signal-behavior')]
    fig2, ax = plt.subplots(figsize=(9, 10))
    by = {(r['original_id'], r['expression'], r['condition']): r for r in rows}
    cells = [(e, c) for e in ['A', 'B'] for c in ['S', 'K', 'I', 'C']]
    matrix = np.asarray([[MODES.index(by[oid, e, c]['probe_pred']) for e, c in cells] for oid in base_ids])
    ax.imshow(matrix, cmap=ListedColormap(['#287ca3', '#e5b74c', '#b34b60']), vmin=-.5, vmax=2.5, aspect='auto')
    ax.set_xticks(range(8), [e + '/' + c for e, c in cells])
    ax.set_yticks(range(30), [r['base_id'] for r in bases])
    ax.axvline(3.5, color='white', linewidth=2)
    for i in range(1, 30):
        ax.axhline(i - .5, color='white', linewidth=.3)
    ax.set_title('Frozen old L28 class across all eight variants\n'
        'Readout classes only; no semantic accuracy or causal claim')
    legend = [Line2D([], [], marker='s', markersize=10, linestyle='',
        color=color, label=label) for color, label in zip(['#287ca3', '#e5b74c', '#b34b60'], MODES)]
    ax.legend(handles=legend, loc='upper center', bbox_to_anchor=(.5, -.035), ncol=3, frameon=False)
    fig2.tight_layout(rect=(0, .03, 1, 1))
    figures.append((fig2, '-probe-classes'))
    for figure, suffix in figures:
        for extension in ['png', 'pdf']:
            stream = io.BytesIO()
            metadata = {'CreationDate': None, 'ModDate': None} if extension == 'pdf' else {}
            figure.savefig(stream, format=extension, dpi=170, metadata=metadata)
            write_artifact(root / (PREFIX + suffix + '.' + extension), stream.getvalue(), stage)
        plt.close(figure)


def write_artifact(path, data, stage):
    if path.exists():
        review.require(path.read_bytes() == data, 'Artifact differs; refuse overwrite: ' + str(path))
    else:
        review.require(stage == 'analyze', 'Missing artifact: ' + str(path))
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['analyze', 'verify'], required=True)
    args = parser.parse_args()
    report, pairs, bases, rows = build()
    outputs = {PREFIX + '.json': review.json_bytes(report),
        PREFIX + '-pairs.csv': csv_bytes(pairs), PREFIX + '-bases.csv': csv_bytes(bases)}
    for name, data in outputs.items():
        write_artifact(ROOT / name, data, args.stage)
    plots(ROOT, report, pairs, bases, rows, args.stage)
    print(json.dumps(dict(stage=args.stage, pairs=len(pairs), bases=len(bases),
        author_reference_eligible=174, new_gpu_calls=0, independent_gold=False)))


if __name__ == '__main__':
    main()
