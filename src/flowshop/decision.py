"""Write decision.json in the structure of data/worked-example/solution.json.

{"sequence": [job ids], "schedule": [{"job_id", "stage_id", "start", "completion"}, ...]}
Schedule entries are listed job by job in sequence order, and stage by stage within a
job. Times are written exactly as computed: json writes floats with full precision.
"""

from __future__ import annotations

import json
from pathlib import Path

from flowshop.loader import Instance
from flowshop.schedule import Times


def build_decision(instance: Instance, sequence: list[str], times: Times) -> dict:
    schedule = []
    for job_id in sequence:
        for stage_id in instance.stages:
            start, completion = times[(job_id, stage_id)]
            schedule.append(
                {"job_id": job_id, "stage_id": stage_id, "start": start, "completion": completion}
            )
    return {"sequence": list(sequence), "schedule": schedule}


def write_decision(path: Path, decision: dict) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(decision, f, indent=2)
        f.write("\n")
