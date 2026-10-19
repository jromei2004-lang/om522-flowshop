"""Load one option 6 instance directory and run the four input checks.

The four checks come from the project guide (Section 2.2) and DATA_DICTIONARY.md:
  1. every required file and column is present,
  2. every value has the type schema.json declares, and non-nullable columns are filled,
  3. every identifier referenced from another file exists,
  4. processing times are positive.
A few structural checks (unique ids, one time per job-stage pair, stage sequence 1..n)
are added because the problem is undefined without them.

Every problem found is collected and raised together as an InputError, so the user
sees all of them at once. Each message names the file and column. Values are never
filled in, rounded, or replaced.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

JOBS = "jobs.csv"
STAGES = "stages.csv"
TIMES = "processing_times.csv"
SCHEMA = "schema.json"

# Required files and columns, from DATA_DICTIONARY.md. "id" columns hold identifiers,
# "numeric" columns must be declared integer or number in schema.json.
REQUIRED_COLUMNS = {
    JOBS: {"job_id": "id", "release_time": "numeric", "due_date": "numeric", "weight": "numeric"},
    STAGES: {"stage_id": "id", "sequence": "numeric"},
    TIMES: {"job_id": "id", "stage_id": "id", "processing_time": "numeric"},
}

KNOWN_TYPES = {"string", "integer", "number"}
INTEGER_PATTERN = re.compile(r"[+-]?\d+")
NUMBER_PATTERN = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")


class InputError(Exception):
    """The instance failed one or more input checks. `problems` lists every message."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


@dataclass(frozen=True)
class Job:
    job_id: str
    release_time: float
    due_date: float
    weight: float


@dataclass(frozen=True)
class Instance:
    jobs: dict[str, Job]                           # keyed by job_id, in jobs.csv row order
    stages: list[str]                              # stage_ids in processing order (by sequence)
    processing_time: dict[tuple[str, str], float]  # (job_id, stage_id) -> time


def load_instance(input_dir: Path) -> Instance:
    """Read and validate an instance directory. Raises InputError if anything is wrong."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise InputError([f"{input_dir}: input directory not found"])

    problems: list[str] = []
    schema = _read_schema(input_dir, problems)

    # Checks 1 and 2, one file at a time. A file that fails check 1 is skipped for
    # check 2, but the other files are still checked.
    tables: dict[str, list[dict]] = {}
    for file_name in REQUIRED_COLUMNS:
        rows = _read_typed_rows(input_dir, file_name, schema, problems)
        if rows is not None:
            tables[file_name] = rows

    # Checks 3 and 4 and the structural checks need all three files.
    if len(tables) == len(REQUIRED_COLUMNS):
        instance = _build_instance(tables, problems)
    else:
        instance = None

    if problems:
        raise InputError(problems)
    return instance


def _read_schema(input_dir: Path, problems: list[str]) -> dict | None:
    """Return {file: {column: (type, nullable)}} from schema.json, or None on failure."""
    path = input_dir / SCHEMA
    if not path.is_file():
        problems.append(f"{SCHEMA}: required file is missing")
        return None
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
        declared = {}
        for file_name, info in raw["files"].items():
            declared[file_name] = {
                col["name"]: (col["type"], col["nullable"]) for col in info["columns"]
            }
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        problems.append(f"{SCHEMA}: cannot read the file list and column types ({exc})")
        return None

    ok = True
    for file_name, columns in REQUIRED_COLUMNS.items():
        for column, kind in columns.items():
            if column not in declared.get(file_name, {}):
                problems.append(f"{SCHEMA}: no type declared for {file_name}, column {column}")
                ok = False
                continue
            col_type, _ = declared[file_name][column]
            if col_type not in KNOWN_TYPES:
                problems.append(f"{SCHEMA}: {file_name}, column {column} has unknown type '{col_type}'")
                ok = False
            elif kind == "numeric" and col_type == "string":
                problems.append(
                    f"{SCHEMA}: {file_name}, column {column} must be declared integer or number, not string"
                )
                ok = False
    return declared if ok else None


def _read_typed_rows(
    input_dir: Path, file_name: str, schema: dict | None, problems: list[str]
) -> list[dict] | None:
    """Check 1 (file and columns present) and check 2 (types) for one CSV file.

    Returns the rows with values converted, or None if the file could not be checked.
    Each row also carries its line number in the file under the key "_line".
    """
    path = input_dir / file_name
    if not path.is_file():
        problems.append(f"{file_name}: required file is missing")
        return None

    # utf-8-sig is UTF-8 that also ignores the byte-order mark Excel adds when saving
    # CSV. Without it the first header would read as "﻿job_id".
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        body = list(reader)
    if header is None:
        problems.append(f"{file_name}: file is empty (no header row)")
        return None

    # Columns schema.json declares must be present too, not only the built-in list.
    declared = schema.get(file_name, {}) if schema else {}
    needed = list(REQUIRED_COLUMNS[file_name]) + [c for c in declared if c not in REQUIRED_COLUMNS[file_name]]
    missing = [c for c in needed if c not in header]
    for column in missing:
        problems.append(f"{file_name}, column {column}: required column is missing")
    duplicated = sorted({c for c in header if header.count(c) > 1})
    for column in duplicated:
        problems.append(f"{file_name}, column {column}: column appears more than once")
    if missing or duplicated or schema is None:
        return None

    rows = []
    for line_no, cells in enumerate(body, start=2):
        if not cells:
            continue  # a fully blank line carries no data
        if len(cells) != len(header):
            problems.append(
                f"{file_name}, line {line_no}: has {len(cells)} values but the header has {len(header)} columns"
            )
            continue
        raw = dict(zip(header, cells))
        row = {"_line": line_no}
        for column, (col_type, nullable) in declared.items():
            value, error = _convert(raw[column], col_type)
            if error is None and value is None:
                if not nullable:
                    error = "is blank but the column may not be empty"
                elif column in REQUIRED_COLUMNS[file_name]:
                    error = "is blank but scheduling needs this value"
            if error:
                problems.append(f"{file_name}, column {column}, line {line_no}: {error}")
            row[column] = value
        rows.append(row)
    return rows


def _convert(text: str, col_type: str):
    """Convert one cell. Returns (value, error message or None). Blank gives (None, None)."""
    if text == "":
        return None, None
    if col_type == "string":
        return text, None
    if col_type == "integer":
        if INTEGER_PATTERN.fullmatch(text):
            return int(text), None
        return None, f"value '{text}' is not an integer"
    # col_type == "number"
    if NUMBER_PATTERN.fullmatch(text):
        value = float(text)
        if math.isfinite(value):
            return value, None
    return None, f"value '{text}' is not a number"


def _build_instance(tables: dict[str, list[dict]], problems: list[str]) -> Instance | None:
    """Check 3 (identifiers exist), check 4 (positive times), and the structural checks."""
    start_count = len(problems)

    # Jobs: unique ids.
    jobs: dict[str, Job] = {}
    for row in tables[JOBS]:
        job_id = row["job_id"]
        if job_id is None:
            continue
        if job_id in jobs:
            problems.append(f"{JOBS}, column job_id, line {row['_line']}: job '{job_id}' appears more than once")
            continue
        jobs[job_id] = Job(job_id, row["release_time"], row["due_date"], row["weight"])

    # Stages: unique ids, and sequence values are exactly 1, 2, ..., number of stages.
    stage_seq: dict[str, int] = {}
    for row in tables[STAGES]:
        stage_id = row["stage_id"]
        if stage_id is None:
            continue
        if stage_id in stage_seq:
            problems.append(
                f"{STAGES}, column stage_id, line {row['_line']}: stage '{stage_id}' appears more than once"
            )
            continue
        stage_seq[stage_id] = row["sequence"]
    seq_values = sorted(v for v in stage_seq.values() if v is not None)
    if seq_values != list(range(1, len(stage_seq) + 1)):
        problems.append(
            f"{STAGES}, column sequence: values must be 1, 2, ..., {len(stage_seq)} with no gaps or repeats "
            f"(found {seq_values})"
        )

    # Processing times: ids exist (check 3), times positive (check 4), one row per pair.
    times: dict[tuple[str, str], float] = {}
    for row in tables[TIMES]:
        job_id, stage_id, p = row["job_id"], row["stage_id"], row["processing_time"]
        line = row["_line"]
        if job_id is not None and job_id not in jobs:
            problems.append(f"{TIMES}, column job_id, line {line}: job '{job_id}' is not in {JOBS}")
        if stage_id is not None and stage_id not in stage_seq:
            problems.append(f"{TIMES}, column stage_id, line {line}: stage '{stage_id}' is not in {STAGES}")
        if p is not None and p <= 0:
            problems.append(
                f"{TIMES}, column processing_time, line {line}: job {job_id} at stage {stage_id} "
                f"has {row['processing_time']} (must be positive)"
            )
        if job_id is None or stage_id is None:
            continue
        if (job_id, stage_id) in times:
            problems.append(
                f"{TIMES}, columns job_id and stage_id, line {line}: "
                f"job {job_id} at stage {stage_id} appears more than once"
            )
            continue
        times[(job_id, stage_id)] = p

    for job_id in jobs:
        for stage_id in stage_seq:
            if (job_id, stage_id) not in times:
                problems.append(
                    f"{TIMES}, columns job_id and stage_id: no processing time for job {job_id} at stage {stage_id}"
                )

    if len(problems) > start_count:
        return None
    stages = sorted(stage_seq, key=stage_seq.get)
    return Instance(jobs=jobs, stages=stages, processing_time=times)
