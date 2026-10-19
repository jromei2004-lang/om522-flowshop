"""Tests for the loader and its four input checks.

Every test that changes an instance works on a copy in pytest's temporary folder,
so nothing under data/ is ever modified.
"""

import csv
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from flowshop.cli import main
from flowshop.loader import InputError, load_instance

DATA = Path(__file__).resolve().parent.parent / "data"
VALID_INSTANCES = [
    "hand_checkable",
    "development_small",
    "development_medium",
    "development_large",
]


def copy_instance(name: str, tmp_path: Path) -> Path:
    target = tmp_path / name
    shutil.copytree(DATA / name, target)
    return target


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def set_cell(path: Path, line: int, column: str, value: str) -> None:
    """Change one cell. line counts like a text editor: header is line 1."""
    rows = read_csv(path)
    rows[line - 1][rows[0].index(column)] = value
    write_csv(path, rows)


def rejection_messages(instance_dir: Path) -> str:
    with pytest.raises(InputError) as err:
        load_instance(instance_dir)
    return "\n".join(err.value.problems)


def run_solve(input_dir: Path, output_dir: Path) -> subprocess.CompletedProcess:
    """Run the real command in a separate process to see its true exit status."""
    return subprocess.run(
        [sys.executable, "-m", "flowshop.cli", str(input_dir), str(output_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------- Required test 2: the supplied edge case is rejected ----------

def test_edge_case_is_rejected(tmp_path):
    out = tmp_path / "out"
    result = run_solve(DATA / "edge_case", out)
    assert result.returncode != 0
    assert "processing_times.csv, column processing_time" in result.stderr
    assert "job J001 at stage S1" in result.stderr
    assert not (out / "decision.json").exists()


# ---------- Required test 3: a deleted required column is rejected ----------

def test_deleted_required_column_is_rejected(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    rows = read_csv(inst / "jobs.csv")
    col = rows[0].index("due_date")
    write_csv(inst / "jobs.csv", [r[:col] + r[col + 1:] for r in rows])

    out = tmp_path / "out"
    result = run_solve(inst, out)
    assert result.returncode != 0
    assert "jobs.csv, column due_date: required column is missing" in result.stderr
    assert not (out / "decision.json").exists()


# ---------- Valid instances load ----------

@pytest.mark.parametrize("name", VALID_INSTANCES)
def test_valid_instances_load(name):
    instance = load_instance(DATA / name)
    n_stages = 4 if name == "hand_checkable" else 8
    assert len(instance.stages) == n_stages
    assert len(instance.processing_time) == len(instance.jobs) * n_stages


def test_hand_checkable_values():
    instance = load_instance(DATA / "hand_checkable")
    assert list(instance.jobs) == ["J001", "J002", "J003", "J004", "J005", "J006"]
    assert instance.stages == ["S1", "S2", "S3", "S4"]
    j1 = instance.jobs["J001"]
    assert (j1.release_time, j1.due_date, j1.weight) == (13, 43, 2)
    # From the worked example: J001 runs 13 to 24 on S1.
    assert instance.processing_time[("J001", "S1")] == 11


def test_shuffled_rows_give_same_instance(tmp_path):
    original = load_instance(DATA / "development_small")
    inst = copy_instance("development_small", tmp_path)
    rng = random.Random(0)
    for file_name in ["stages.csv", "processing_times.csv"]:
        rows = read_csv(inst / file_name)
        body = rows[1:]
        rng.shuffle(body)
        write_csv(inst / file_name, [rows[0]] + body)
    shuffled = load_instance(inst)
    assert shuffled.stages == original.stages
    assert shuffled.processing_time == original.processing_time
    assert shuffled.jobs == original.jobs


def test_decimal_times_kept_at_full_precision(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    schema = (inst / "schema.json").read_text(encoding="utf-8")
    schema = schema.replace(
        '"name": "processing_time",\n          "type": "integer"',
        '"name": "processing_time",\n          "type": "number"',
    )
    (inst / "schema.json").write_text(schema, encoding="utf-8")
    set_cell(inst / "processing_times.csv", 2, "processing_time", "11.123456789012")
    instance = load_instance(inst)
    assert instance.processing_time[("J001", "S1")] == 11.123456789012


# ---------- Check 1: files and columns present ----------

def test_missing_file(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    (inst / "stages.csv").unlink()
    assert "stages.csv: required file is missing" in rejection_messages(inst)


def test_missing_schema(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    (inst / "schema.json").unlink()
    assert "schema.json: required file is missing" in rejection_messages(inst)


def test_missing_input_directory(tmp_path):
    assert "input directory not found" in rejection_messages(tmp_path / "nope")


# ---------- Check 2: types and blanks ----------

def test_text_in_integer_column(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "jobs.csv", 3, "release_time", "abc")
    assert "jobs.csv, column release_time, line 3: value 'abc' is not an integer" in rejection_messages(inst)


def test_decimal_in_integer_column(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "jobs.csv", 2, "weight", "2.5")
    assert "jobs.csv, column weight, line 2: value '2.5' is not an integer" in rejection_messages(inst)


def test_blank_cell(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "jobs.csv", 4, "due_date", "")
    assert "jobs.csv, column due_date, line 4: is blank" in rejection_messages(inst)


# ---------- Check 3: referenced identifiers exist ----------

def test_unknown_job_id(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "processing_times.csv", 2, "job_id", "J999")
    msg = rejection_messages(inst)
    assert "processing_times.csv, column job_id, line 2: job 'J999' is not in jobs.csv" in msg


def test_unknown_stage_id(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "processing_times.csv", 2, "stage_id", "S9")
    msg = rejection_messages(inst)
    assert "processing_times.csv, column stage_id, line 2: stage 'S9' is not in stages.csv" in msg


# ---------- Check 4: positive processing times ----------

def test_negative_processing_time(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "processing_times.csv", 5, "processing_time", "-3")
    msg = rejection_messages(inst)
    assert "processing_times.csv, column processing_time, line 5" in msg
    assert "must be positive" in msg


# ---------- Structural checks ----------

def test_duplicate_job_id(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "jobs.csv", 3, "job_id", "J001")
    assert "jobs.csv, column job_id, line 3: job 'J001' appears more than once" in rejection_messages(inst)


def test_missing_job_stage_pair(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    rows = read_csv(inst / "processing_times.csv")
    write_csv(inst / "processing_times.csv", rows[:-1])  # drop the last pair
    assert "no processing time for job" in rejection_messages(inst)


def test_stage_sequence_gap(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "stages.csv", 5, "sequence", "7")
    assert "stages.csv, column sequence" in rejection_messages(inst)


def test_short_row_names_the_missing_column(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    rows = read_csv(inst / "jobs.csv")
    rows[2] = rows[2][:-1]  # line 3 loses its weight
    write_csv(inst / "jobs.csv", rows)
    assert "jobs.csv, column weight, line 3: no value" in rejection_messages(inst)


def test_long_row_names_the_last_column(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    rows = read_csv(inst / "jobs.csv")
    rows[2].append("99")
    write_csv(inst / "jobs.csv", rows)
    assert "jobs.csv, line 3: 1 extra values after the last column, weight" in rejection_messages(inst)


@pytest.mark.parametrize("file_name, message", [
    ("jobs.csv", "jobs.csv, column job_id: no jobs"),
    ("stages.csv", "stages.csv, column stage_id: no stages"),
])
def test_header_only_file_is_rejected(tmp_path, file_name, message):
    inst = copy_instance("hand_checkable", tmp_path)
    write_csv(inst / file_name, read_csv(inst / file_name)[:1])
    assert message in rejection_messages(inst)


def test_non_ascii_digits_are_not_an_integer(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "jobs.csv", 2, "release_time", "\u0661\u0663")  # Arabic-Indic "13"
    assert "jobs.csv, column release_time, line 2: value" in rejection_messages(inst)


def test_extra_column_with_unknown_type_is_rejected(tmp_path):
    import json
    inst = copy_instance("hand_checkable", tmp_path)
    rows = read_csv(inst / "jobs.csv")
    write_csv(inst / "jobs.csv", [r + (["ship_date"] if i == 0 else ["2026-10-19"]) for i, r in enumerate(rows)])
    schema_path = inst / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["files"]["jobs.csv"]["columns"].append({"name": "ship_date", "type": "date", "nullable": False})
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    assert "schema.json: jobs.csv, column ship_date has unknown type 'date'" in rejection_messages(inst)


def test_all_problems_reported_together(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_cell(inst / "jobs.csv", 2, "weight", "x")
    set_cell(inst / "processing_times.csv", 3, "processing_time", "0")
    with pytest.raises(InputError) as err:
        load_instance(inst)
    assert len(err.value.problems) == 2


# ---------- Command line behavior ----------

def test_stale_decision_removed_on_bad_input(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "decision.json").write_text("{}", encoding="utf-8")
    assert main([str(DATA / "edge_case"), str(out)]) == 1
    assert not (out / "decision.json").exists()


def test_valid_input_exits_zero_and_writes_decision(tmp_path):
    # Guard for required tests 2 and 3: valid input does write decision.json, so their
    # "no decision.json" assertions can actually fail if rejection is broken.
    out = tmp_path / "out"
    assert main([str(DATA / "hand_checkable"), str(out)]) == 0
    assert (out / "decision.json").is_file()
    assert (out / "summary.txt").is_file()


def test_output_same_as_input_refused(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    assert main([str(inst), str(inst)]) == 1


def test_output_inside_input_refused(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    before = sorted(p.name for p in inst.iterdir())
    assert main([str(inst), str(inst / "out")]) == 1
    assert sorted(p.name for p in inst.iterdir()) == before


def test_output_beside_input_allowed(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    assert main([str(inst), str(tmp_path / "hand_checkable_out")]) == 0


def test_input_files_unchanged(tmp_path):
    before = {p.name: p.read_bytes() for p in (DATA / "edge_case").iterdir()}
    main([str(DATA / "edge_case"), str(tmp_path / "out")])
    after = {p.name: p.read_bytes() for p in (DATA / "edge_case").iterdir()}
    assert before == after
