"""Method 2, Iterated Greedy (Ruiz and Stützle 2007, EJOR) for total weighted tardiness.

Steps:
  1. Start from the EDD sequence (the rule to beat).
  2. NEH-style insertion (Nawaz, Enscore, and Ham 1983): take jobs in EDD order and
     insert each into the position of the partial sequence with the lowest weighted
     tardiness, then apply local search. The search starts from this sequence.
  3. Repeat for a fixed number of iterations:
       destruction:  remove d jobs chosen at random (seeded),
       construction: reinsert them one by one, each at its best position,
       local search: iterative improvement by insertion (each job in random order is
                     removed and reinserted at its best position; repeat until a full
                     pass finds no improvement),
       acceptance:   keep a better sequence; keep an equal or worse one with
                     probability exp(-(candidate - current) / T).
  4. Return the best sequence seen. EDD itself counts as seen, so the result is never
     worse than the rule to beat.

Our adaptations (also in the README):
  - Temperature: Ruiz and Stützle use T = Tp * (sum of processing times) / (n * m * 10),
    which is in minutes, for makespan. Weighted tardiness is in weighted minutes, so we
    multiply by the average weight.
  - NEH order: the original NEH inserts jobs by decreasing total processing time (a
    makespan idea). We insert in EDD order, because due dates drive tardiness.
  - With Tp = 0 the temperature is 0 and only strict improvements are accepted (not
    used by default or in the tuning grid).

Ties between insertion positions go to the earliest position. Stopping: a fixed number
of iterations. The time limit is only a safety cap, checked before each iteration (not
during the initial NEH and local search), and is reported if it is ever reached.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

import numpy as np

from flowshop.fast_eval import Arrays, insertion_costs, prefix_states, to_arrays, weighted_tardiness
from flowshop.loader import Instance
from flowshop.rule_to_beat import edd_sequence
from flowshop.schedule import Times, build_schedule, total_weighted_tardiness


def _improves(new: float, old: float) -> bool:
    """True if new is lower than old by more than rounding noise (relative 1e-9)."""
    return new < old - 1e-9 * max(1.0, abs(old))


@dataclass(frozen=True)
class Settings:
    # Provisional defaults until tuning picks them.
    iterations: int = 1000
    d: int = 4
    seed: int = 522
    tp: float = 0.4
    time_limit: float = 480.0  # seconds, safety cap only


@dataclass(frozen=True)
class Checkpoint:
    sequence: list[str]   # best sequence seen after this many iterations
    iterations_done: int
    elapsed: float        # seconds since solve started
    stop_reason: str


@dataclass
class Result:
    sequence: list[str]
    times: Times
    twt: float                 # recomputed from schedule.py
    edd_twt: float
    start_twt: float           # after NEH and local search, before the iterations
    iterations_done: int
    stop_reason: str
    temperature: float
    d_used: int                # d after limiting it to the number of jobs
    checkpoints: dict[int, Checkpoint] = field(default_factory=dict)


class EvaluationMismatch(RuntimeError):
    """The fast evaluation disagreed with schedule.py. Should never happen."""


def _best_insert(seq: np.ndarray, job: int, A: Arrays) -> tuple[np.ndarray, float]:
    F, cum = prefix_states(seq, A.P, A.R, A.D, A.W)
    costs = insertion_costs(seq, job, F, cum, A.P, A.R, A.D, A.W, True)
    pos = int(np.argmin(costs))  # first minimum, so ties go to the earliest position
    return np.insert(seq, pos, job), float(costs[pos])


def _local_search(seq: np.ndarray, value: float, A: Arrays, rng: random.Random) -> tuple[np.ndarray, float]:
    """Iterative improvement by insertion, until a full pass finds no improvement."""
    improved = True
    while improved:
        improved = False
        order = [int(j) for j in seq]
        rng.shuffle(order)
        for job in order:
            idx = int(np.flatnonzero(seq == job)[0])
            candidate, cand_value = _best_insert(np.delete(seq, idx), job, A)
            if _improves(cand_value, value):
                seq, value, improved = candidate, cand_value, True
    return seq, value


def solve(instance: Instance, settings: Settings = Settings(), checkpoints=()) -> Result:
    """Run Iterated Greedy. `checkpoints` lists iteration counts at which to record the
    best sequence so far (used by tuning; a checkpoint at k equals a k-iteration run)."""
    started = time.perf_counter()
    A = to_arrays(instance)
    n, m = A.P.shape
    rng = random.Random(settings.seed)
    index = {job_id: i for i, job_id in enumerate(A.job_ids)}
    wanted = set(checkpoints)
    recorded: dict[int, Checkpoint] = {}

    edd = np.array([index[j] for j in edd_sequence(instance)], dtype=np.int64)
    edd_value = float(weighted_tardiness(edd, A.P, A.R, A.D, A.W))

    # NEH-style construction from the EDD order, then local search. The search starts
    # here (as in the paper); EDD only competes for best-so-far.
    current = edd[:1].copy()
    for job in edd[1:]:
        current, _ = _best_insert(current, int(job), A)
    current_value = float(weighted_tardiness(current, A.P, A.R, A.D, A.W))
    current, current_value = _local_search(current, current_value, A, rng)
    start_value = current_value
    best, best_value = (current, current_value) if _improves(current_value, edd_value) else (edd, edd_value)

    mean_weight = float(A.W.mean()) if n else 0.0
    temperature = settings.tp * mean_weight * float(A.P.sum()) / max(1, n * m * 10)
    d = min(settings.d, n)

    def ids(seq):
        return [A.job_ids[int(j)] for j in seq]

    def record(done: int, reason: str):
        if done in wanted:
            recorded[done] = Checkpoint(ids(best), done, time.perf_counter() - started, reason)

    iterations_done = 0
    if n <= 1:
        stop_reason = "no search needed (fewer than 2 jobs)"
    else:
        stop_reason = f"iteration count reached ({settings.iterations})"
        for _ in range(settings.iterations):
            if time.perf_counter() - started > settings.time_limit:
                stop_reason = f"SAFETY TIME CAP reached ({settings.time_limit:.0f} s); result may not reproduce"
                break
            removed = rng.sample([int(j) for j in current], d)
            removed_set = set(removed)
            partial = np.array([j for j in current if int(j) not in removed_set], dtype=np.int64)
            partial_value = float(weighted_tardiness(partial, A.P, A.R, A.D, A.W))
            for job in removed:
                partial, partial_value = _best_insert(partial, job, A)
            candidate, cand_value = _local_search(partial, partial_value, A, rng)

            if _improves(cand_value, current_value):
                current, current_value = candidate, cand_value
                if _improves(cand_value, best_value):
                    best, best_value = candidate, cand_value
            elif temperature > 0 and rng.random() <= math.exp(-(cand_value - current_value) / temperature):
                current, current_value = candidate, cand_value
            iterations_done += 1
            record(iterations_done, f"iteration count reached ({iterations_done})")
    for k in wanted - recorded.keys():  # checkpoints not reached (cap, or fewer than 2 jobs)
        recorded[k] = Checkpoint(ids(best), iterations_done, time.perf_counter() - started, stop_reason)

    sequence = ids(best)
    times = build_schedule(instance, sequence)
    twt = total_weighted_tardiness(instance, times)
    if abs(twt - best_value) > 1e-6 * max(1.0, abs(twt)):
        raise EvaluationMismatch(f"fast evaluation ({best_value}) disagrees with schedule.py ({twt})")

    # Guarantee on the reported (schedule.py) value, not only the fast value.
    edd_ids = ids(edd)
    edd_times = build_schedule(instance, edd_ids)
    edd_twt = total_weighted_tardiness(instance, edd_times)
    if twt > edd_twt:
        sequence, times, twt = edd_ids, edd_times, edd_twt

    return Result(
        sequence=sequence,
        times=times,
        twt=twt,
        edd_twt=edd_twt,
        start_twt=start_value,
        iterations_done=iterations_done,
        stop_reason=stop_reason,
        temperature=temperature,
        d_used=d,
        checkpoints=recorded,
    )
