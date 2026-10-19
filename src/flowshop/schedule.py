"""Turn a job sequence into stage-level start and completion times, and compute measures.

This is method-side code shared by the rule to beat and the researched method. The
independent checker must not import it.

Timing (option 6 brief, "Rule to beat"): each operation starts at the later of
  - the job's completion at the previous stage (or its release, at the first stage), and
  - the stage's completion of the previous job in the sequence.
Completion = start + processing time. Times are never rounded.
"""

from __future__ import annotations

from flowshop.loader import Instance

# (job_id, stage_id) -> (start, completion)
Times = dict[tuple[str, str], tuple[float, float]]


def build_schedule(instance: Instance, sequence: list[str]) -> Times:
    """Earliest start times for every operation when every stage uses `sequence`."""
    machine_free: dict[str, float | None] = {s: None for s in instance.stages}  # None: no job yet
    times: Times = {}
    for job_id in sequence:
        ready = instance.jobs[job_id].release_time
        for stage_id in instance.stages:
            free = machine_free[stage_id]
            start = ready if free is None else max(ready, free)
            completion = start + instance.processing_time[(job_id, stage_id)]
            times[(job_id, stage_id)] = (start, completion)
            machine_free[stage_id] = completion
            ready = completion
    return times


def total_weighted_tardiness(instance: Instance, times: Times) -> float:
    """Sum over jobs of weight * max(0, completion at the last stage - due date)."""
    last = instance.stages[-1]
    return sum(
        job.weight * max(0, times[(job.job_id, last)][1] - job.due_date)
        for job in instance.jobs.values()
    )


def total_waiting(instance: Instance, times: Times) -> float:
    """Sum over jobs and every stage after the first of start minus previous completion."""
    return sum(
        times[(job_id, stage)][0] - times[(job_id, prev)][1]
        for job_id in instance.jobs
        for prev, stage in zip(instance.stages, instance.stages[1:])
    )
