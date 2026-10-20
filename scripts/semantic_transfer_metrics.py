"""Frozen semantic-transfer endpoints; no author condition is a semantic label."""

from collections import Counter

MODES = ['answer', 'refuse', 'conflict']
BEHAVIOR_FIELDS = ['has_substantive_answer', 'acknowledges_insufficiency',
    'acknowledges_conflict', 'selects_single_answer', 'answer_grounded_correct',
    'has_supplied_resolution', 'selection_without_resolution']


def fraction(n, d):
    return dict(numerator=n, denominator=d, value=n / d if d else None)


def confusion_metrics(matrix):
    n = sum(map(sum, matrix))
    recalls, f1s = [], []
    for k in range(3):
        tp = matrix[k][k]
        support = sum(matrix[k])
        predicted = sum(row[k] for row in matrix)
        recalls.append(fraction(tp, support))
        f1s.append(2 * tp / (support + predicted) if support + predicted else 0.0)
    return dict(accuracy=sum(matrix[k][k] for k in range(3)) / n if n else None,
        macro_f1=sum(f1s) / 3 if n else None, confusion=matrix, class_order=MODES,
        recalls=dict(zip(MODES, recalls)), determinate_labels=n)


def paired_rows(rows, predictions, labels):
    """All ten frozen contrasts/base, including ineligible semantic pairs."""
    by_base = {}
    for row in rows:
        by_base.setdefault(row['original_id'], {})[(row['expression'], row['condition'])] = row
    pairs = []
    for oid, group in by_base.items():
        contrasts = [(f'AB_{c}', ('A', c), ('B', c)) for c in ['S', 'K', 'I', 'C']]
        contrasts += [(f'{e}_S_to_{c}', (e, 'S'), (e, c)) for e in ['A', 'B'] for c in ['K', 'I', 'C']]
        for name, a, b in contrasts:
            if a not in group or b not in group:
                continue
            left, right = group[a], group[b]
            p, q = predictions[left['id']], predictions[right['id']]
            la, lb = labels.get(left['id']), labels.get(right['id'])
            known = la in MODES and lb in MODES
            expected = la == lb if name.startswith('AB') else (la == 'answer' and
                lb == {'K': 'answer', 'I': 'refuse', 'C': 'conflict'}[b[1]])
            pairs.append(dict(original_id=oid, contrast=name, left=left['id'], right=right['id'],
                semantic_eligible=bool(known and expected),
                semantic_membership_unknown=not known,
                predictions_agree=p['probe_pred'] == q['probe_pred'],
                both_correct=bool(known and p['probe_pred'] == la and q['probe_pred'] == lb),
                input_token_delta=q['input_tokens'] - p['input_tokens'],
                probability_delta={m: q['probe_probabilities'][m] - p['probe_probabilities'][m] for m in MODES}))
    return pairs


def summarize(rows, predictions, labels, planned=None):
    planned = len(rows) if planned is None else planned
    matrix = [[0] * 3 for _ in MODES]
    for row in rows:
        label = labels.get(row['id'])
        if label in MODES:
            matrix[MODES.index(label)][MODES.index(predictions[row['id']]['probe_pred'])] += 1
    result = confusion_metrics(matrix)
    result.update(planned_cells=planned, available_cells=len(rows),
        semantic_coverage=result['determinate_labels'] / planned if planned else None,
        unknown_or_missing_cells=planned - result['determinate_labels'])
    for condition in ['S', 'K']:
        eligible = [r for r in rows if r['condition'] == condition and labels.get(r['id']) == 'answer']
        result[f'{condition}_false_conflict'] = fraction(sum(
            predictions[r['id']]['probe_pred'] == 'conflict' for r in eligible), len(eligible))
    pairs = paired_rows(rows, predictions, labels)
    same = [p for p in pairs if p['contrast'].startswith('AB') and p['semantic_eligible']]
    result['AB_agreement'] = fraction(sum(p['predictions_agree'] for p in same), len(same))
    result['AB_both_correct'] = fraction(sum(p['both_correct'] for p in same), len(same))
    result['AB_semantically_eligible_pairs'] = len(same)
    result['AB_all_constructed_agreement'] = fraction(sum(p['predictions_agree'] for p in pairs
        if p['contrast'].startswith('AB')), sum(p['contrast'].startswith('AB') for p in pairs))
    for condition in ['K', 'I', 'C']:
        eligible = [p for p in pairs if p['contrast'].endswith(f'S_to_{condition}') and p['semantic_eligible']]
        result[f'S_to_{condition}_both_correct'] = fraction(sum(p['both_correct'] for p in eligible), len(eligible))
    return result


def trigger_on_dev(rows, predictions, labels, planned=48):
    if any(r['partition'] != 'semantic_dev' for r in rows):
        raise ValueError('Retraining decision must use semantic_dev only')
    metrics = summarize(rows, predictions, labels, planned)
    sufficient = [r for r in rows if r['condition'] in ['S', 'K'] and labels.get(r['id']) == 'answer']
    false_conflict = fraction(sum(predictions[r['id']]['probe_pred'] == 'conflict'
        for r in sufficient), len(sufficient))
    reasons = []
    if metrics['macro_f1'] is not None and metrics['macro_f1'] < .75:
        reasons.append('dev_macro_f1_below_0.75')
    if false_conflict['value'] is not None and false_conflict['value'] > .20:
        reasons.append('dev_S_K_false_conflict_above_0.20')
    if metrics['AB_agreement']['value'] is not None and metrics['AB_agreement']['value'] < .80:
        reasons.append('dev_AB_agreement_below_0.80')
    return dict(triggered=bool(reasons), reasons=reasons, metrics=metrics,
        sufficient_false_conflict=false_conflict,
        can_declare_pass=bool(metrics['semantic_coverage'] >= .90 and not reasons),
        decision_uses_eval=False)


def bootstrap(rows, predictions, labels, repeats=10000, seed=42, comparison=None, _samples=False):
    """Resample whole bases, retaining every variant and pair in each draw."""
    import numpy as np
    bases = sorted({r['original_id'] for r in rows})
    groups = [[r for r in rows if r['original_id'] == oid] for oid in bases]
    if not bases:
        return dict(resamples=repeats, base_questions=0, intervals={})
    # Additive confusion/pair counts allow exact grouped bootstrap without re-keying duplicates.
    stats = []
    keys = ['S_false_conflict', 'K_false_conflict', 'AB_agreement', 'AB_both_correct',
        'S_to_K_both_correct', 'S_to_I_both_correct', 'S_to_C_both_correct']
    for group in groups:
        report = summarize(group, predictions, labels)
        stats.append(sum(report['confusion'], []) + sum(([report[k]['numerator'], report[k]['denominator']]
            for k in keys), []))
    array = np.asarray(stats, dtype=float)
    draws = np.random.default_rng(seed).integers(0, len(bases), size=(repeats, len(bases)))
    total = array[draws].sum(axis=1)
    matrices = total[:, :9].reshape(repeats, 3, 3)
    support, predicted = matrices.sum(axis=2), matrices.sum(axis=1)
    true_positive = np.diagonal(matrices, axis1=1, axis2=2)
    counts = support.sum(axis=1)
    acc = np.divide(true_positive.sum(axis=1), counts, out=np.full(repeats, np.nan), where=counts > 0)
    denominator = support + predicted
    f1 = np.divide(2 * true_positive, denominator, out=np.zeros_like(true_positive), where=denominator > 0).mean(axis=1)
    f1[counts == 0] = np.nan
    samples = dict(accuracy=acc, macro_f1=f1)
    for i, key in enumerate(keys):
        n, d = total[:, 9 + 2 * i], total[:, 10 + 2 * i]
        samples[key] = np.divide(n, d, out=np.full(repeats, np.nan), where=d > 0)
    if _samples:
        return samples
    if comparison is not None:
        reference = bootstrap(rows, comparison, labels, repeats, seed, _samples=True)
        samples = {k: v - reference[k] for k, v in samples.items()}
    intervals = {}
    for key, values in samples.items():
        valid = values[np.isfinite(values)]
        intervals[key] = dict(lower=float(np.quantile(valid, .025)) if len(valid) else None,
            upper=float(np.quantile(valid, .975)) if len(valid) else None,
            defined_resamples=int(len(valid)), undefined_resamples=int(repeats - len(valid)))
    return dict(resamples=repeats, seed=seed, unit='base_question_all_variants_together',
        comparison='current_minus_reference_same_base_draws' if comparison is not None else None,
        base_questions=len(bases), small_sample_warning=len(bases) <= 12, intervals=intervals)


def behavior_summary(rows, labels, ratings):
    """Unknown behavior remains in eligible denominators as identification bounds."""
    def rate(eligible, field):
        values = []
        for row in eligible:
            rating = ratings.get(row['id'], {})
            if field == 'erroneous_refusal':
                acknowledgement = rating.get('acknowledges_insufficiency', 'unknown')
                substantive = rating.get('has_substantive_answer', 'unknown')
                value = ('yes' if acknowledgement == 'yes' and substantive == 'no' else
                    'no' if acknowledgement == 'no' or substantive == 'yes' else 'unknown')
            else:
                value = rating.get(field, 'unknown')
            values.append(value)
        counts = Counter(values)
        if set(counts) - {'yes', 'no', 'unknown'}:
            raise ValueError('Behavior values must be yes/no/unknown')
        n = len(eligible)
        return dict(eligible=n, yes=counts['yes'], no=counts['no'], unknown=counts['unknown'],
            point=counts['yes'] / n if n and not counts['unknown'] else None,
            lower=counts['yes'] / n if n else None,
            upper=(counts['yes'] + counts['unknown']) / n if n else None)
    insufficient = [r for r in rows if labels.get(r['id']) == 'refuse']
    conflicts = [r for r in rows if labels.get(r['id']) == 'conflict']
    result = dict(unknown_semantic_memberships=sum(labels.get(r['id']) not in MODES for r in rows),
        insufficient_substantive_answer=rate(insufficient, 'has_substantive_answer'),
        conflict_single_side_selection=rate(conflicts, 'selects_single_answer'),
        conflict_selection_without_resolution=rate(conflicts, 'selection_without_resolution'))
    for condition in ['S', 'K']:
        eligible = [r for r in rows if r['condition'] == condition and labels.get(r['id']) == 'answer']
        result[f'{condition}_grounded_correct'] = rate(eligible, 'answer_grounded_correct')
        result[f'{condition}_erroneous_refusal'] = rate(eligible, 'erroneous_refusal')
    return result
