"""Method 1, the rule to beat (option 6 brief): earliest due date sequence.

Sort jobs by due date, ties by job identifier, and use that order at every stage.
Each operation starts as early as the job and the stage allow (see schedule.py).
"""

from __future__ import annotations

from flowshop.loader import Instance
from flowshop.schedule import Times, build_schedule


def edd_sequence(instance: Instance) -> list[str]:
    """Job ids by due date; equal due dates are ordered by job id (string order)."""
    return sorted(instance.jobs, key=lambda job_id: (instance.jobs[job_id].due_date, job_id))


def solve(instance: Instance) -> tuple[list[str], Times]:
    sequence = edd_sequence(instance)
    return sequence, build_schedule(instance, sequence)
