"""The numba evaluation must match schedule.py (the plain-Python reference) exactly."""

import random
from pathlib import Path

import numpy as np
import pytest

from flowshop.fast_eval import (
    insertion_costs,
    prefix_states,
    schedule_times,
    to_arrays,
    weighted_tardiness,
)
from flowshop.loader import load_instance
from flowshop.rule_to_beat import edd_sequence
from flowshop.schedule import build_schedule, total_weighted_tardiness

DATA = Path(__file__).resolve().parent.parent / "data"
INSTANCES = ["hand_checkable", "development_small", "development_medium", "development_large"]


def sequences_to_test(instance, count=5):
    """The EDD sequence plus a few seeded random orders."""
    rng = random.Random(1)
    seqs = [edd_sequence(instance)]
    for _ in range(count):
        s = list(instance.jobs)
        rng.shuffle(s)
        seqs.append(s)
    return seqs


@pytest.mark.parametrize("name", INSTANCES)
def test_times_and_tardiness_match_schedule_py(name):
    instance = load_instance(DATA / name)
    A = to_arrays(instance)
    index = {j: i for i, j in enumerate(A.job_ids)}
    for seq in sequences_to_test(instance):
        ref = build_schedule(instance, seq)
        arr = np.array([index[j] for j in seq], dtype=np.int64)
        S, C = schedule_times(arr, A.P, A.R)
        for i, job_id in enumerate(seq):
            for k, stage_id in enumerate(instance.stages):
                assert (S[i, k], C[i, k]) == ref[(job_id, stage_id)], (job_id, stage_id)
        assert weighted_tardiness(arr, A.P, A.R, A.D, A.W) == total_weighted_tardiness(instance, ref)


@pytest.mark.parametrize("name", INSTANCES)
def test_prefix_shortcut_matches_full_recompute(name):
    """Every insertion cost from the prefix shortcut equals schedule.py on the full sequence."""
    instance = load_instance(DATA / name)
    A = to_arrays(instance)
    index = {j: i for i, j in enumerate(A.job_ids)}
    rng = random.Random(2)
    for seq in sequences_to_test(instance, count=2):
        job_id = seq[rng.randrange(len(seq))]
        rest = [j for j in seq if j != job_id]
        arr = np.array([index[j] for j in rest], dtype=np.int64)
        F, cum = prefix_states(arr, A.P, A.R, A.D, A.W)

        exact = insertion_costs(arr, index[job_id], F, cum, A.P, A.R, A.D, A.W, False)
        for pos in range(len(rest) + 1):
            full = rest[:pos] + [job_id] + rest[pos:]
            assert exact[pos] == total_weighted_tardiness(instance, build_schedule(instance, full)), pos

        # Pruning skips hopeless positions but must pick the same best position and cost.
        pruned = insertion_costs(arr, index[job_id], F, cum, A.P, A.R, A.D, A.W, True)
        assert int(np.argmin(pruned)) == int(np.argmin(exact))
        assert pruned.min() == exact.min()
