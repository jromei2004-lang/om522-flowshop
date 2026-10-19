"""Independent checker: pixi run check <input_dir> <decision.json>

Reads only the instance CSV files and one decision.json, checks every required
constraint from the option 6 brief, and recomputes the measures from the decision's
own start and completion times.

Independence: this module imports nothing from the flowshop package, not even the
loader, so a bug shared by the methods (in reading, stage order, or timing) cannot
also hide here. Numbers a decision file reports about itself (any key other than
sequence and schedule) are ignored.

Constraints checked, each with tolerance 1e-8 as in the guide, Section 4.3:
  - every input job appears exactly once in the sequence, and no other job does;
  - every job-stage pair appears exactly once in the schedule, and no other pair does;
  - completion minus start equals the processing time;
  - a job starts its first stage no earlier than its release, and each later stage no
    earlier than its completion at the previous stage;
  - no two jobs overlap on a stage (start inclusive, completion exclusive);
  - the order of jobs on every stage is the sequence.

Exit status: 0 feasible, 1 infeasible, 2 the input files or decision file cannot be read.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOL = 1e-8

JOBS = "jobs.csv"
STAGES = "stages.csv"
TIMES = "processing_times.csv"


class CannotCheck(Exception):
    """The input files or the decision file cannot be read at all."""


@dataclass
class Violation:
    rule: str
    message: str
    job_id: str | None = None
    stage_id: str | None = None

    def __str__(self) -> str:
        where = ", ".join(p for p in (
            f"job {self.job_id}" if self.job_id else "",
            f"stage {self.stage_id}" if self.stage_id else "",
        ) if p)
        return f"[{self.rule}] {where + ': ' if where else ''}{self.message}"


@dataclass
class CheckResult:
    violations: list[Violation] = field(default_factory=list)
    measures: dict[str, float] | None = None   # None when the schedule is incomplete
    ignored_keys: list[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return not self.violations

    def add(self, rule: str, message: str, job_id: str | None = None, stage_id: str | None = None) -> None:
        self.violations.append(Violation(rule, message, job_id, stage_id))


# ---------- reading the input (independent of flowshop.loader) ----------

def _read_csv(path: Path, columns: list[str]) -> list[tuple[int, dict[str, str]]]:
    """Return (line number in the file, row) pairs. Blank lines are skipped."""
    if not path.is_file():
        raise CannotCheck(f"{path.name}: required file is missing")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for col in columns:
            if col not in header:
                raise CannotCheck(f"{path.name}, column {col}: required column is missing")
        return [(reader.line_num, row) for row in reader]


def _number(text: str | None, file: str, column: str, line: int) -> float:
    try:
        value = float(text)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise CannotCheck(f"{file}, column {column}, line {line}: value '{text}' is not a number") from None
    if not math.isfinite(value):
        raise CannotCheck(f"{file}, column {column}, line {line}: value '{text}' is not finite")
    return int(value) if value.is_integer() else value


def _identifier(text: str | None, file: str, column: str, line: int) -> str:
    if not text:
        raise CannotCheck(f"{file}, column {column}, line {line}: identifier is blank")
    return text


def read_input(input_dir: Path):
    """Return (jobs, stages, p). jobs: id -> (release, due, weight); stages in order; p: (job, stage) -> time."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise CannotCheck(f"{input_dir}: input directory not found")

    jobs: dict[str, tuple[float, float, float]] = {}
    for line, row in _read_csv(input_dir / JOBS, ["job_id", "release_time", "due_date", "weight"]):
        jid = _identifier(row["job_id"], JOBS, "job_id", line)
        if jid in jobs:
            raise CannotCheck(f"{JOBS}, column job_id, line {line}: job '{jid}' appears more than once")
        jobs[jid] = tuple(_number(row[c], JOBS, c, line) for c in ("release_time", "due_date", "weight"))

    if not jobs:
        raise CannotCheck(f"{JOBS}: no jobs")

    seq: dict[str, float] = {}
    for line, row in _read_csv(input_dir / STAGES, ["stage_id", "sequence"]):
        sid = _identifier(row["stage_id"], STAGES, "stage_id", line)
        if sid in seq:
            raise CannotCheck(f"{STAGES}, column stage_id, line {line}: stage '{sid}' appears more than once")
        seq[sid] = _number(row["sequence"], STAGES, "sequence", line)
    if not seq:
        raise CannotCheck(f"{STAGES}: no stages")
    if sorted(seq.values()) != list(range(1, len(seq) + 1)):
        raise CannotCheck(f"{STAGES}, column sequence: values must be 1, 2, ..., {len(seq)}")
    stages = sorted(seq, key=seq.get)

    p: dict[tuple[str, str], float] = {}
    for line, row in _read_csv(input_dir / TIMES, ["job_id", "stage_id", "processing_time"]):
        key = (_identifier(row["job_id"], TIMES, "job_id", line), _identifier(row["stage_id"], TIMES, "stage_id", line))
        if key[0] not in jobs:
            raise CannotCheck(f"{TIMES}, column job_id, line {line}: job '{key[0]}' is not in {JOBS}")
        if key[1] not in seq:
            raise CannotCheck(f"{TIMES}, column stage_id, line {line}: stage '{key[1]}' is not in {STAGES}")
        if key in p:
            raise CannotCheck(f"{TIMES}, line {line}: job {key[0]} at stage {key[1]} appears more than once")
        value = _number(row["processing_time"], TIMES, "processing_time", line)
        if value <= 0:
            raise CannotCheck(
                f"{TIMES}, column processing_time, line {line}: job {key[0]} at stage {key[1]} "
                f"has {row['processing_time']} (must be positive)"
            )
        p[key] = value
    for jid in jobs:
        for sid in stages:
            if (jid, sid) not in p:
                raise CannotCheck(f"{TIMES}: no processing time for job {jid} at stage {sid}")
    return jobs, stages, p


def read_decision(path: Path) -> object:
    path = Path(path)
    if not path.is_file():
        raise CannotCheck(f"{path}: decision file not found")
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CannotCheck(f"{path.name}: not valid JSON ({exc})") from None


# ---------- checking ----------

def _is_time(value: object) -> bool:
    # JSON true/false load as bool, which Python counts as int; reject them explicitly.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check(input_dir: Path, decision_path: Path) -> CheckResult:
    jobs, stages, p = read_input(input_dir)
    return check_decision(jobs, stages, p, read_decision(decision_path))


def check_decision(jobs, stages, p, decision: object) -> CheckResult:
    result = CheckResult()
    if not isinstance(decision, dict):
        result.add("structure", "decision file must be a JSON object with 'sequence' and 'schedule'")
        return result
    result.ignored_keys = sorted(k for k in decision if k not in ("sequence", "schedule"))

    # Sequence: each input job exactly once, nothing else.
    sequence = decision.get("sequence")
    seq_ok = isinstance(sequence, list)
    if not seq_ok:
        result.add("structure", "'sequence' is missing or is not a list")
        sequence = []
    seen: set[str] = set()
    for pos, jid in enumerate(sequence, 1):
        if not isinstance(jid, str):
            result.add("sequence", f"position {pos} holds {jid!r}, not a job id")
            seq_ok = False
        elif jid not in jobs:
            result.add("sequence", "unknown job id (not in jobs.csv)", jid)
            seq_ok = False
        elif jid in seen:
            result.add("sequence", f"appears more than once (again at position {pos})", jid)
            seq_ok = False
        else:
            seen.add(jid)
    if isinstance(decision.get("sequence"), list):
        for jid in jobs:
            if jid not in seen:
                result.add("sequence", "job from jobs.csv is missing from the sequence", jid)
                seq_ok = False

    # Schedule: each job-stage pair exactly once with a numeric start and completion.
    schedule = decision.get("schedule")
    if not isinstance(schedule, list):
        result.add("structure", "'schedule' is missing or is not a list")
        schedule = []
    times: dict[tuple[str, str], tuple[float, float]] = {}
    for i, entry in enumerate(schedule, 1):
        if not isinstance(entry, dict):
            result.add("structure", f"schedule entry {i} is not an object")
            continue
        missing = [k for k in ("job_id", "stage_id", "start", "completion") if k not in entry]
        if missing:
            result.add("structure", f"schedule entry {i} is missing {', '.join(missing)}",
                       entry.get("job_id") if isinstance(entry.get("job_id"), str) else None,
                       entry.get("stage_id") if isinstance(entry.get("stage_id"), str) else None)
            continue
        jid, sid, s, c = entry["job_id"], entry["stage_id"], entry["start"], entry["completion"]
        if not isinstance(jid, str) or not isinstance(sid, str):
            result.add("structure", f"schedule entry {i}: job_id {jid!r} and stage_id {sid!r} must be strings")
            continue
        if jid not in jobs:
            result.add("schedule", f"schedule entry {i} has unknown job id {jid!r} (not in jobs.csv)", jid, sid)
            continue
        if sid not in stages:
            result.add("schedule", f"schedule entry {i} has unknown stage id {sid!r} (not in stages.csv)", jid, sid)
            continue
        if not (_is_time(s) and _is_time(c)):
            result.add("structure", f"start {s!r} and completion {c!r} must both be finite numbers", jid, sid)
            continue
        if (jid, sid) in times:
            result.add("schedule", "job-stage pair appears more than once in the schedule", jid, sid)
            continue
        times[(jid, sid)] = (s, c)
    complete = True
    for jid in jobs:
        for sid in stages:
            if (jid, sid) not in times:
                result.add("schedule", "job-stage pair is missing from the schedule", jid, sid)
                complete = False

    # Constraints on the operations that are present.
    for (jid, sid), (s, c) in times.items():
        if abs((c - s) - p[(jid, sid)]) > TOL:
            result.add("duration", f"completion - start = {c} - {s} = {c - s}, "
                       f"but processing_times.csv gives {p[(jid, sid)]}", jid, sid)
    for jid, (release, _, _) in jobs.items():
        first = (jid, stages[0])
        if first in times and times[first][0] < release - TOL:
            result.add("release", f"starts at {times[first][0]}, before its release {release}", jid, stages[0])
        for prev, cur in zip(stages, stages[1:]):
            if (jid, prev) in times and (jid, cur) in times:
                prev_c, cur_s = times[(jid, prev)][1], times[(jid, cur)][0]
                if cur_s < prev_c - TOL:
                    result.add("stage order", f"starts at {cur_s}, before it completes stage {prev} at {prev_c}",
                               jid, cur)

    for sid in stages:
        ops = sorted((times[(j, sid)][0], times[(j, sid)][1], j) for j in jobs if (j, sid) in times)
        busy = None  # (start, completion, job) of the operation finishing latest so far
        for s2, c2, j2 in ops:
            if busy is not None and s2 < busy[1] - TOL:
                s1, c1, j1 = busy
                result.add("overlap", f"runs [{s2}, {c2}) while job {j1} runs [{s1}, {c1}) on the same stage",
                           j2, sid)
            if busy is None or c2 > busy[1]:
                busy = (s2, c2, j2)
        if seq_ok and complete:
            order = [j for _, _, j in ops]
            if order != sequence:
                pos = next(k for k, (a, b) in enumerate(zip(order, sequence)) if a != b)
                result.add("same sequence", f"position {pos + 1} on this stage is job {order[pos]}, "
                           f"but the sequence has job {sequence[pos]} there", order[pos], sid)

    if complete:
        last = stages[-1]
        result.measures = {
            "total_weighted_tardiness": sum(
                w * max(0, times[(j, last)][1] - due) for j, (_, due, w) in jobs.items()),
            "total_waiting": sum(
                times[(j, cur)][0] - times[(j, prev)][1]
                for j in jobs for prev, cur in zip(stages, stages[1:])),
            "makespan": max(c for _, c in times.values()),
        }
    return result


# ---------- command line ----------

MAX_SHOWN = 50


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check", description="Independent checker for an option 6 decision.json")
    parser.add_argument("input_dir", type=Path, help="instance directory")
    parser.add_argument("decision", type=Path, help="decision.json to check")
    args = parser.parse_args(argv)

    try:
        result = check(args.input_dir, args.decision)
    except CannotCheck as err:
        print(f"Cannot check: {err}", file=sys.stderr)
        return 2

    print(f"Checking {args.decision} against {args.input_dir}")
    if result.ignored_keys:
        print(f"Ignored keys the decision reports about itself: {', '.join(result.ignored_keys)}")
    if result.feasible:
        print("Status: FEASIBLE (every required constraint holds)")
    else:
        print(f"Status: INFEASIBLE ({len(result.violations)} violations)")
        for v in result.violations[:MAX_SHOWN]:
            print(f"  - {v}")
        if len(result.violations) > MAX_SHOWN:
            print(f"  ... and {len(result.violations) - MAX_SHOWN} more")
    if result.measures is not None:
        note = "" if result.feasible else " (decision is infeasible; shown for diagnosis only)"
        print(f"Recomputed measures{note}:")
        print(f"  Total weighted tardiness: {result.measures['total_weighted_tardiness']}")
        print(f"  Total waiting between stages: {result.measures['total_waiting']}")
        print(f"  Makespan: {result.measures['makespan']}")
    return 0 if result.feasible else 1


if __name__ == "__main__":
    sys.exit(main())
