"""D-057 bounded train-only pilot helpers; see the existing M1 contract.

Algorithms, targets and losses are reused. The array-builder callback captures
exactly its emitted online rows, avoiding a second implementation of row order.
"""
from collections import defaultdict
import hashlib

import numpy as np

from .m1_af_rollout import rollout_learning_arrays_from_audits, training_inner_dev_mask
from .m1_role_encoding import ENCODINGS, encode_online


def partition(plan):
    groups = list(range(plan['start_group_index'], plan['start_group_index'] + plan['paired_groups']))
    dev = [g for g in groups if int.from_bytes(hashlib.sha256(
        f'rollout-pair:train:{g:06d}'.encode()).digest()[:8], 'big') % 5 == 0]
    fit = [g for g in groups if g not in dev]
    if fit != plan['fit_group_indices'] or dev != plan['dev_group_indices'] or not fit or not dev:
        raise ValueError('frozen paired-group partition mismatch')
    return fit, dev


def encoded_arrays(hard, audits, index):
    if len(audits) != 2 or {a['sibling_index'] for a in audits} != {0, 1} or any(
        a['split'] != 'train' or a['paired_group_id'] != f'rollout-pair:train:{index:06d}'
        or len(a['steps']) != 20 for a in audits
    ):
        raise ValueError('pilot requires one complete registered train pair')
    vectors = {mode: [] for mode in ENCODINGS}
    def capture(online):
        for mode in ENCODINGS:
            vectors[mode].append(encode_online(online, encoding=mode))
        return vectors['pooled_v1'][-1]
    base = rollout_learning_arrays_from_audits(hard, audits, future_hash_bins=32, feature_encoder=capture)
    base['group'][:] = index
    if len(base['y']) != 40 or int(base['recovery'].sum()) != 2:
        raise ValueError('pilot learning/recovery row count changed')
    return {mode: {**base, 'x': np.stack(vectors[mode])} for mode in ENCODINGS}


def split_arrays(arrays, plan):
    fit, dev = partition(plan)
    if set(np.unique(arrays['group']).tolist()) != set(fit + dev):
        raise ValueError('incomplete pilot groups')
    mask = training_inner_dev_mask(arrays)
    if set(arrays['group'][mask].tolist()) != set(dev):
        raise ValueError('inner-dev implementation differs from frozen assignment')
    return ({k: v[~mask] for k, v in arrays.items()}, {k: v[mask] for k, v in arrays.items()})


def error_diagnostics(sequences):
    """Report onset denominators separately from persistent world errors."""
    families = defaultdict(lambda: {'eligible': 0, 'new_active_errors': 0,
                                    'identity_confusions': 0, 'selected_labels_on_error': {}})
    c10 = {'decisions': 0, 'index_disagrees_active_correct': 0}
    for sequence in sequences:
        previous_correct = True
        for choice in sequence['choices']:
            family = choice['scenario_family']
            correct = choice['active_correct_after'] == 1.0
            if family == 'C10':
                c10['decisions'] += 1
                c10['index_disagrees_active_correct'] += int(correct and not choice['registered_selection_correct'])
            if previous_correct and choice['ambiguity'] != 'epistemically_ambiguous_pivot':
                row = families[family]
                row['eligible'] += 1
                if not correct:
                    row['new_active_errors'] += 1
                    label = choice.get('selected_program_label', choice['selected_template'])
                    row['selected_labels_on_error'][label] = row['selected_labels_on_error'].get(label, 0) + 1
                    row['identity_confusions'] += int((family, label) in [('C06', 'RELINK'), ('C08', 'REPLACE')])
            previous_correct = correct
    for row in families.values():
        row['new_active_error_rate'] = row['new_active_errors'] / row['eligible'] if row['eligible'] else None
    return {'family_onsets': dict(families), 'c10_index_active_disagreement': c10}


def paired_differences(left, right, groups):
    """Average sibling differences within each group; never treat seeds as groups."""
    lrows = {r['metrics']['sequence_id']: r['metrics'] for r in left}
    rrows = {r['metrics']['sequence_id']: r['metrics'] for r in right}
    if len(lrows) != len(left) or len(rrows) != len(right) or lrows.keys() != rrows.keys():
        raise ValueError('duplicate or unmatched sequences')
    keys = ['final_active_graph_correctness', 'final_open_memory_correctness',
            'final_graded_open_memory_correctness', 'open_fact_error_auc_per_100_decisions']
    differences = {}
    for g in groups:
        ids = [sid for sid, row in lrows.items() if row['paired_group_id'] == f'rollout-pair:train:{g:06d}']
        if len(ids) != 2 or any(lrows[sid]['paired_group_id'] != rrows[sid]['paired_group_id'] for sid in ids):
            raise ValueError('paired comparison missing/mismatched sibling')
        differences[str(g)] = {k: sum(float(lrows[sid][k]) - float(rrows[sid][k]) for sid in ids) / 2 for k in keys}
    if not differences or len(left) != 2 * len(groups):
        raise ValueError('comparison group set differs')
    return {'by_paired_group': differences,
            'mean': {k: sum(row[k] for row in differences.values()) / len(differences) for k in keys}}
