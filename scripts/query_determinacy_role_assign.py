"""Assign evidence roles using coverage constraints and model choice scores."""

from itertools import permutations

import query_determinacy_typed_holdout as base


frozen = base.frozen
require = base.require


def assign(public, rows):
    scores = {row['id']: frozen.choice_scores(row) for row in rows}
    locations, failures = {}, {}
    for name, profile in public['profiles'].items():
        version_candidates = {}
        for tag, text in profile['evidence'].items():
            days = frozen.parse_days(text)
            if len(days) != 2 or days[0] > days[1]:
                continue
            try:
                frozen.amount(text)
            except ValueError:
                continue
            version_candidates[tag] = days
        ranked = []
        for earlier, later in permutations(sorted(version_candidates), 2):
            if version_candidates[earlier][1] >= version_candidates[later][0]:
                continue
            remaining = sorted(set(profile['evidence']) - {earlier, later})
            if len(remaining) != 2:
                continue
            for rule, scope in permutations(remaining):
                roles = {'rule': rule, 'scope': scope, 'earlier': earlier, 'later': later}
                total = sum(scores[f'{name}/{role}'][tag] for role, tag in roles.items())
                ranked.append((total, roles))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            failures[name] = 'no_nonoverlapping_version_pair'
        elif len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            failures[name] = 'role_assignment_tie'
        else:
            locations[name] = ranked[0][1]
    return locations, failures
