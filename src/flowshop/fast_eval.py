"""Compiled (numba) versions of the timing in schedule.py. A speed tool only.

schedule.py is the plain-Python reference. These functions apply the same rule with the
same arithmetic (start = max(job ready, machine free), completion = start + processing
time), and tests/test_fast_eval.py checks that they give exactly the same start times,
completions, and weighted tardiness as schedule.py.

Jobs are referred to by index (their position in Instance.jobs) and stages by their
position in Instance.stages. A stage with no job yet is free at -inf, so
max(ready, -inf) = ready, which matches schedule.py's "no previous job" case.
Weighted tardiness is summed job by job in sequence order.

cache=True stores the compiled code in __pycache__, so it compiles once per machine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from flowshop.loader import Instance


@dataclass(frozen=True)
class Arrays:
    job_ids: list[str]  # index -> job_id
    P: np.ndarray       # processing time [job index, stage position]
    R: np.ndarray       # release time [job index]
    D: np.ndarray       # due date [job index]
    W: np.ndarray       # weight [job index]


def to_arrays(instance: Instance) -> Arrays:
    job_ids = list(instance.jobs)
    jobs = [instance.jobs[j] for j in job_ids]
    P = np.array(
        [[instance.processing_time[(j, s)] for s in instance.stages] for j in job_ids],
        dtype=np.float64,
    ).reshape(len(job_ids), len(instance.stages))
    return Arrays(
        job_ids=job_ids,
        P=P,
        R=np.array([job.release_time for job in jobs], dtype=np.float64),
        D=np.array([job.due_date for job in jobs], dtype=np.float64),
        W=np.array([job.weight for job in jobs], dtype=np.float64),
    )


@njit(cache=True)
def schedule_times(seq, P, R):
    """Start and completion of every operation, rows in sequence order, columns by stage."""
    L = seq.shape[0]
    m = P.shape[1]
    S = np.empty((L, m))
    C = np.empty((L, m))
    free = np.full(m, -np.inf)
    for i in range(L):
        j = seq[i]
        ready = R[j]
        for k in range(m):
            start = max(ready, free[k])
            ready = start + P[j, k]
            S[i, k] = start
            C[i, k] = ready
            free[k] = ready
    return S, C


@njit(cache=True)
def prefix_states(seq, P, R, D, W):
    """For each prefix length i (0..L): when each stage becomes free, and the weighted
    tardiness of the jobs in that prefix. Used by the prefix shortcut."""
    L = seq.shape[0]
    m = P.shape[1]
    F = np.full((L + 1, m), -np.inf)
    cum = np.zeros(L + 1)
    for i in range(L):
        j = seq[i]
        ready = R[j]
        for k in range(m):
            ready = max(ready, F[i, k]) + P[j, k]
            F[i + 1, k] = ready
        tard = ready - D[j]
        cum[i + 1] = cum[i] + (W[j] * tard if tard > 0 else 0.0)
    return F, cum


@njit(cache=True)
def weighted_tardiness(seq, P, R, D, W):
    """Total weighted tardiness of a full (or partial) sequence."""
    _, cum = prefix_states(seq, P, R, D, W)
    return cum[seq.shape[0]]


@njit(cache=True)
def insertion_costs(seq, job, F, cum, P, R, D, W, prune):
    """Weighted tardiness of `seq` with `job` inserted at each position 0..L.

    Prefix shortcut: inserting at position pos leaves the jobs before pos unchanged, so
    each position starts from the saved stage-free times F[pos] and tardiness cum[pos]
    and only recomputes the inserted job and the jobs after it.

    With prune=True, a position stops early once its running total reaches the best
    total found so far (tardiness can only grow as jobs are added), and its cost is left
    at +inf. The best position and its cost are unchanged; ties go to the earliest
    position. With prune=False every position gets its exact cost (used by tests).
    """
    L = seq.shape[0]
    m = P.shape[1]
    costs = np.full(L + 1, np.inf)
    free = np.empty(m)
    best = np.inf
    for pos in range(L + 1):
        total = cum[pos]
        if prune and total >= best:
            continue
        for k in range(m):
            free[k] = F[pos, k]
        ready = R[job]
        for k in range(m):
            ready = max(ready, free[k]) + P[job, k]
            free[k] = ready
        tard = ready - D[job]
        if tard > 0:
            total += W[job] * tard
        stopped = False
        for i in range(pos, L):
            if prune and total >= best:
                stopped = True
                break
            j = seq[i]
            ready = R[j]
            for k in range(m):
                ready = max(ready, free[k]) + P[j, k]
                free[k] = ready
            tard = ready - D[j]
            if tard > 0:
                total += W[j] * tard
        if stopped or (prune and total >= best):
            continue
        costs[pos] = total
        if total < best:
            best = total
    return costs
