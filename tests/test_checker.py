"""Tests for the independent checker (src/flowshop/checker.py)."""

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from flowshop import checker
from flowshop.cli import main as solve_main

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HAND = DATA / "hand_checkable"
SOLUTION = DATA / "worked-example" / "solution.json"


def read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> Path:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def entry(decision: dict, job_id: str, stage_id: str) -> dict:
    return next(e for e in decision["schedule"] if e["job_id"] == job_id and e["stage_id"] == stage_id)


def run_check(input_dir: Path, decision_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "flowshop.checker", str(input_dir), str(decision_path)],
        capture_output=True, text=True, encoding="utf-8",
    )


# ---------- Independence ----------

def test_checker_imports_no_flowshop_code():
    tree = ast.parse((ROOT / "src" / "flowshop" / "checker.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            if node.level:
                imported.add("relative import")
    bad = {m for m in imported if m.split(".")[0] == "flowshop" or m == "relative import"}
    assert not bad, f"checker imports project code: {bad}"
    source = (ROOT / "src" / "flowshop" / "checker.py").read_text(encoding="utf-8")
    assert "importlib" not in source and "__import__" not in source


def test_running_checker_loads_no_other_flowshop_module():
    # Catches imports added to flowshop/__init__.py, which runs before the checker.
    code = "import sys, flowshop.checker; print(sorted(m for m in sys.modules if m.startswith('flowshop')))"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "['flowshop', 'flowshop.checker']"


# ---------- (a) worked example ----------

def test_worked_example_is_feasible_with_reference_measures():
    result = checker.check(HAND, SOLUTION)
    assert result.feasible, [str(v) for v in result.violations]
    assert result.measures == {"total_weighted_tardiness": 281, "total_waiting": 13, "makespan": 139}

    metrics = read_json(DATA / "worked-example" / "metrics.json")
    assert abs(result.measures["total_weighted_tardiness"] - metrics["total_weighted_tardiness"]) < 1e-9
    assert abs(result.measures["total_waiting"] - metrics["downstream_waiting_time"]) < 1e-9
    assert abs(result.measures["makespan"] - metrics["makespan"]) < 1e-9


def test_check_command_exit_zero_on_feasible():
    result = run_check(HAND, SOLUTION)
    assert result.returncode == 0
    assert "FEASIBLE" in result.stdout and "INFEASIBLE" not in result.stdout
    assert "Total weighted tardiness: 281" in result.stdout


# ---------- (b) rule's decision on development_small ----------

def test_rule_decision_on_development_small_is_feasible(tmp_path):
    out = tmp_path / "out_rule"
    assert solve_main([str(DATA / "development_small"), str(out), "--method", "rule"]) == 0
    result = checker.check(DATA / "development_small", out / "decision.json")
    assert result.feasible, [str(v) for v in result.violations]
    assert result.measures["total_weighted_tardiness"] == 1417


@pytest.mark.parametrize("name", ["development_medium", "development_large"])
def test_rule_decision_feasible_on_other_dev_instances(tmp_path, name):
    out = tmp_path / "out"
    assert solve_main([str(DATA / name), str(out), "--method", "rule"]) == 0
    assert checker.check(DATA / name, out / "decision.json").feasible


# ---------- (c) one start time changed ----------

def test_changed_start_time_is_infeasible_and_named(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J003", "S2")["start"] = 73  # was 72; completion stays 75
    path = write_json(tmp_path / "decision.json", d)

    result = checker.check(HAND, path)
    assert not result.feasible
    assert any(v.rule == "duration" and v.job_id == "J003" and v.stage_id == "S2" for v in result.violations)

    proc = run_check(HAND, path)
    assert proc.returncode == 1
    assert "INFEASIBLE (1 violation)" in proc.stdout and "job J003, stage S2" in proc.stdout


@pytest.mark.parametrize("shift", [5e-9, -5e-9])
def test_duration_within_1e8_is_accepted(tmp_path, shift):
    d = read_json(SOLUTION)
    entry(d, "J004", "S4")["completion"] = 139 + shift  # last job, last stage: nothing downstream
    assert checker.check(HAND, write_json(tmp_path / "d.json", d)).feasible


@pytest.mark.parametrize("shift", [5e-8, -5e-8])
def test_duration_beyond_1e8_is_rejected(tmp_path, shift):
    d = read_json(SOLUTION)
    entry(d, "J004", "S4")["completion"] = 139 + shift
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert [(v.rule, v.job_id, v.stage_id) for v in result.violations] == [("duration", "J004", "S4")]


# Each case moves one operation by `e` so exactly one rule is at its boundary.
TOLERANCE_CASES = {
    # J001 starts S1 e before its release (13).
    "release": lambda d, e: entry(d, "J001", "S1").update(start=13 - e, completion=24 - e),
    # J003 completes S2 e after it starts S3 (75).
    "stage order": lambda d, e: entry(d, "J003", "S2").update(start=72 + e, completion=75 + e),
    # J002 completes S4 e after J005 starts there (73); the duration is also off by e.
    "overlap": lambda d, e: entry(d, "J002", "S4").update(completion=73 + e),
}


@pytest.mark.parametrize("rule", sorted(TOLERANCE_CASES))
def test_boundary_within_1e8_is_accepted(tmp_path, rule):
    d = read_json(SOLUTION)
    TOLERANCE_CASES[rule](d, 5e-9)
    assert checker.check(HAND, write_json(tmp_path / "d.json", d)).feasible


@pytest.mark.parametrize("rule", sorted(TOLERANCE_CASES))
def test_boundary_beyond_1e8_is_rejected(tmp_path, rule):
    d = read_json(SOLUTION)
    TOLERANCE_CASES[rule](d, 5e-8)
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert rule in {v.rule for v in result.violations}


# ---------- (d) sequence swapped but schedule unchanged ----------

def test_swapped_sequence_is_infeasible(tmp_path):
    d = read_json(SOLUTION)
    q = d["sequence"]
    q[1], q[2] = q[2], q[1]
    path = write_json(tmp_path / "decision.json", d)

    result = checker.check(HAND, path)
    assert not result.feasible
    assert {v.rule for v in result.violations} == {"same sequence"}
    assert {v.stage_id for v in result.violations} == {"S1", "S2", "S3", "S4"}
    assert {(v.job_id, v.other_job_id) for v in result.violations} == {("J002", "J005")}
    proc = run_check(HAND, path)
    assert proc.returncode == 1
    assert "INFEASIBLE (4 violations)" in proc.stdout
    assert "[same sequence] jobs J002 and J005, stage S1:" in proc.stdout


# ---------- Other constraint violations ----------

def test_start_before_release(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J001", "S1").update(start=12, completion=23)  # J001 released at 13
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert any(v.rule == "release" and v.job_id == "J001" and v.stage_id == "S1" for v in result.violations)


def test_start_before_previous_stage_completes(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J001", "S2").update(start=23, completion=33)  # S1 completes at 24
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert any(v.rule == "stage order" and v.job_id == "J001" and v.stage_id == "S2" for v in result.violations)


def test_overlap_on_a_stage(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J002", "S1").update(start=23, completion=37)  # J001 runs [13, 24) on S1
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    overlaps = [v for v in result.violations if v.rule == "overlap"]
    assert [(v.job_id, v.other_job_id, v.stage_id) for v in overlaps] == [("J002", "J001", "S1")]
    assert "job J001" in overlaps[0].message


def test_overlap_reports_every_job_inside_a_long_operation(tmp_path):
    d = read_json(SOLUTION)
    # J001 occupies S4 from 40 to 200, so J002 [60, 73) and J005 [73, 82) both run inside it.
    entry(d, "J001", "S4").update(start=40, completion=200)
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    named = {v.job_id for v in result.violations if v.rule == "overlap" and v.stage_id == "S4"}
    assert {"J002", "J005", "J003", "J006", "J004"} <= named


# ---------- Malformed decision files ----------

def test_unknown_job_in_sequence_and_schedule(tmp_path):
    d = read_json(SOLUTION)
    d["sequence"][0] = "J999"
    entry(d, "J001", "S1")["job_id"] = "J999"
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert not result.feasible
    assert any(v.rule == "sequence" and v.job_id == "J999" and "unknown job id" in v.message
               for v in result.violations)
    assert any(v.rule == "schedule" and v.job_id == "J999" and "unknown job id" in v.message
               for v in result.violations)
    assert any(v.job_id == "J001" and "missing from the sequence" in v.message for v in result.violations)


def test_extra_job_not_in_input(tmp_path):
    d = read_json(SOLUTION)
    d["sequence"].append("J007")
    d["schedule"].append({"job_id": "J007", "stage_id": "S1", "start": 200, "completion": 210})
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert not result.feasible
    assert sum("J007" in str(v) for v in result.violations) == 2


def test_unknown_stage(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J001", "S4")["stage_id"] = "S9"
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert any("S9" in v.message for v in result.violations)
    assert any(v.job_id == "J001" and v.stage_id == "S4" and "missing" in v.message for v in result.violations)


@pytest.mark.parametrize("field", ["job_id", "stage_id", "start", "completion"])
def test_missing_field_in_schedule_entry(tmp_path, field):
    d = read_json(SOLUTION)
    del entry(d, "J003", "S2")[field]
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert not result.feasible
    assert any(v.rule == "structure" and field in v.message for v in result.violations)
    assert result.measures is None


@pytest.mark.parametrize("key", ["sequence", "schedule"])
def test_missing_top_level_key(tmp_path, key):
    d = read_json(SOLUTION)
    del d[key]
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert not result.feasible
    assert any(key in v.message for v in result.violations)


@pytest.mark.parametrize("value", [["J001"], {"id": "J001"}, 7])
def test_non_string_job_id_in_schedule(tmp_path, value):
    d = read_json(SOLUTION)
    entry(d, "J001", "S1")["job_id"] = value
    path = write_json(tmp_path / "d.json", d)
    result = checker.check(HAND, path)
    assert any(v.rule == "structure" and "must be strings" in v.message for v in result.violations)
    assert run_check(HAND, path).returncode == 1


@pytest.mark.parametrize("value", ["13", None, True])
def test_non_numeric_start(tmp_path, value):
    d = read_json(SOLUTION)
    entry(d, "J001", "S1")["start"] = value
    assert not checker.check(HAND, write_json(tmp_path / "d.json", d)).feasible


def test_duplicate_and_missing_schedule_entries(tmp_path):
    d = read_json(SOLUTION)
    d["schedule"].append(dict(entry(d, "J001", "S1")))
    d["schedule"].remove(entry(d, "J006", "S3"))
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert any(v.job_id == "J001" and "more than once" in v.message for v in result.violations)
    assert any(v.job_id == "J006" and v.stage_id == "S3" and "missing" in v.message for v in result.violations)


def test_duplicate_job_in_sequence(tmp_path):
    d = read_json(SOLUTION)
    d["sequence"][5] = d["sequence"][0]
    result = checker.check(HAND, write_json(tmp_path / "d.json", d))
    assert any(v.job_id == "J001" and "more than once" in v.message for v in result.violations)
    assert any(v.job_id == "J004" and "missing" in v.message for v in result.violations)


def test_reported_objective_values_are_ignored(tmp_path):
    d = read_json(SOLUTION)
    d["total_weighted_tardiness"] = 0
    d["measures"] = {"total_waiting": 0, "makespan": 1}
    path = write_json(tmp_path / "d.json", d)
    result = checker.check(HAND, path)
    assert result.feasible
    assert result.measures == {"total_weighted_tardiness": 281, "total_waiting": 13, "makespan": 139}
    assert result.ignored_keys == ["measures", "total_weighted_tardiness"]


# ---------- Unreadable input ----------

def test_invalid_json_exits_2(tmp_path):
    path = tmp_path / "d.json"
    path.write_text("{not json", encoding="utf-8")
    proc = run_check(HAND, path)
    assert proc.returncode == 2
    assert "not valid JSON" in proc.stderr


def test_edge_case_input_cannot_be_checked(tmp_path):
    proc = run_check(DATA / "edge_case", SOLUTION)
    assert proc.returncode == 2
    assert "processing_times.csv, column processing_time" in proc.stderr


@pytest.mark.parametrize("file_name", ["jobs.csv", "stages.csv"])
def test_input_file_with_header_only_exits_2(tmp_path, file_name):
    inst = tmp_path / "inst"
    shutil.copytree(HAND, inst)
    header = (inst / file_name).read_text(encoding="utf-8").splitlines()[0]
    (inst / file_name).write_text(header + "\n", encoding="utf-8")
    proc = run_check(inst, SOLUTION)
    assert proc.returncode == 2
    assert file_name in proc.stderr


def test_blank_identifier_in_input_exits_2(tmp_path):
    inst = tmp_path / "inst"
    shutil.copytree(HAND, inst)
    text = (inst / "jobs.csv").read_text(encoding="utf-8").replace("J006,", ",", 1)
    (inst / "jobs.csv").write_text(text, encoding="utf-8")
    proc = run_check(inst, SOLUTION)
    assert proc.returncode == 2
    assert "jobs.csv, column job_id" in proc.stderr


# ---------- --report output (used by pixi run compare and the charts) ----------

def write_report_for(decision_path: Path, tmp_path: Path, input_dir: Path = HAND) -> tuple[int, dict | None]:
    report_path = tmp_path / "report.json"
    code = checker.main([str(input_dir), str(decision_path), "--report", str(report_path)])
    return code, read_json(report_path) if report_path.is_file() else None


def test_report_matches_worked_example(tmp_path):
    report_path = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, "-m", "flowshop.checker", str(HAND), str(SOLUTION), "--report", str(report_path)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0
    report = read_json(report_path)
    solution = read_json(SOLUTION)
    assert report["feasible"] is True and report["violations"] == []
    assert report["measures"] == {"total_weighted_tardiness": 281, "total_waiting": 13, "makespan": 139}
    assert report["diagnostic_measures"] is None
    assert report["stages"] == ["S1", "S2", "S3", "S4"]
    assert report["sequence"] == solution["sequence"]
    # Same operations, one each, in sequence order then stage order (as solution.json lists them).
    assert report["operations"] == solution["schedule"]


def test_report_operations_and_measures_use_the_same_completions(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J004", "S4")["completion"] = 139 + 5e-9  # within tolerance
    code, report = write_report_for(write_json(tmp_path / "d.json", d), tmp_path)
    assert code == 0
    op = next(o for o in report["operations"] if (o["job_id"], o["stage_id"]) == ("J004", "S4"))
    assert op["completion"] == 139 + 5e-9
    assert report["measures"]["makespan"] == max(o["completion"] for o in report["operations"])


def test_report_stage_order_follows_sequence_column(tmp_path):
    inst = tmp_path / "inst"
    shutil.copytree(HAND, inst)
    lines = (inst / "stages.csv").read_text(encoding="utf-8").splitlines()
    (inst / "stages.csv").write_text("\n".join([lines[0]] + lines[:0:-1]) + "\n", encoding="utf-8")  # S4..S1
    code, report = write_report_for(SOLUTION, tmp_path, inst)
    assert code == 0
    assert report["stages"] == ["S1", "S2", "S3", "S4"]


def test_report_for_infeasible_decision_keeps_the_decision_and_withholds_measures(tmp_path):
    d = read_json(SOLUTION)
    entry(d, "J003", "S2")["start"] = 73
    code, report = write_report_for(write_json(tmp_path / "d.json", d), tmp_path)
    assert code == 1
    assert report["feasible"] is False
    assert [(v["rule"], v["job_id"], v["other_job_id"], v["stage_id"]) for v in report["violations"]] == [
        ("duration", "J003", None, "S2")]
    assert "processing_times.csv gives 3" in report["violations"][0]["message"]
    assert report["measures"] is None
    assert report["diagnostic_measures"]["total_weighted_tardiness"] == 281
    # The flagged operation is reported as the decision has it, not corrected.
    op = next(o for o in report["operations"] if (o["job_id"], o["stage_id"]) == ("J003", "S2"))
    assert (op["start"], op["completion"]) == (73, 75)


def test_report_for_incomplete_decision(tmp_path):
    d = read_json(SOLUTION)
    d["schedule"].remove(entry(d, "J006", "S3"))
    code, report = write_report_for(write_json(tmp_path / "d.json", d), tmp_path)
    assert code == 1
    assert report["operations"] == []
    assert report["measures"] is None and report["diagnostic_measures"] is None
    assert report["sequence"] == d["sequence"]


def test_report_for_invalid_sequence(tmp_path):
    d = read_json(SOLUTION)
    d["sequence"][0] = "J999"
    code, report = write_report_for(write_json(tmp_path / "d.json", d), tmp_path)
    assert code == 1
    assert report["sequence"] is None and report["measures"] is None


def test_report_for_non_object_decision_still_has_stages(tmp_path):
    code, report = write_report_for(write_json(tmp_path / "d.json", [1, 2]), tmp_path)
    assert code == 1
    assert report["stages"] == ["S1", "S2", "S3", "S4"]


def test_stale_report_removed_when_input_cannot_be_checked(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text('{"feasible": true}', encoding="utf-8")
    assert checker.main([str(DATA / "edge_case"), str(SOLUTION), "--report", str(report_path)]) == 2
    assert not report_path.exists()


def test_unwritable_report_exits_3(tmp_path):
    report_dir = tmp_path / "report.json"
    report_dir.mkdir()  # a directory cannot be written as a file
    assert checker.main([str(HAND), str(SOLUTION), "--report", str(report_dir)]) == 3
