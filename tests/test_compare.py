"""Tests for pixi run compare and its charts."""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from flowshop import compare, plots

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOLUTION = DATA / "worked-example" / "solution.json"

needs_pixi = pytest.mark.skipif(shutil.which("pixi") is None, reason="pixi is not on PATH")


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_cpu_name_is_not_empty():
    assert compare.cpu_name().strip()


def test_method_choices_read_from_help_text():
    rule_only = "usage: solve [-h] [--method {rule}] input_dir output_dir"
    both = "usage: solve [-h] [--method {ig,rule}] [--iterations ITERATIONS] input_dir output_dir"
    assert compare.METHOD_CHOICES.search(rule_only).group(1) == "rule"
    assert compare.METHOD_CHOICES.search(both).group(1) == "ig,rule"


@needs_pixi
def test_compare_end_to_end_skips_missing_method(tmp_path, capsys):
    results = tmp_path / "results"
    code = compare.main(["--results-dir", str(results), "--methods", "rule", "not_a_method",
                         "--instances", "hand_checkable", "development_small"])
    assert code == 0
    assert "Skipping not_a_method" in capsys.readouterr().out

    assert b"\r" not in (results / "comparison.csv").read_bytes()
    rows = read_rows(results / "comparison.csv")
    assert list(rows[0]) == compare.COLUMNS
    assert [(r["method"], r["instance"]) for r in rows] == [("rule", "hand_checkable"), ("rule", "development_small")]
    hand, small = rows
    assert hand["feasible"] == "True" and small["feasible"] == "True"
    assert float(hand["total_weighted_tardiness"]) == 281 and float(hand["total_waiting"]) == 13
    assert float(small["total_weighted_tardiness"]) == 1417
    assert (hand["jobs"], hand["stages"]) == ("6", "4")
    assert hand["cpu"] and hand["runtime_s"] != ""
    assert hand["time_limit_s"] == "none"  # the rule has no time limit

    for name in ("gantt_rule_hand_checkable.png", "gantt_rule_development_small.png", "comparison_bars.png"):
        assert (results / "figures" / name).stat().st_size > 0
    assert (results / "runs" / "rule" / "hand_checkable" / "check_report.json").is_file()


def test_infeasible_decision_gets_no_measures_and_no_gantt(tmp_path, monkeypatch):
    """A method that writes a bad decision: the row says infeasible and nothing is charted."""
    def fake_pixi(*args):
        if args[0] == "solve":
            out = Path(args[2])
            out.mkdir(parents=True, exist_ok=True)
            d = json.loads(SOLUTION.read_text(encoding="utf-8"))
            d["schedule"][0]["start"] += 1  # duration no longer matches
            d["total_weighted_tardiness"] = 0  # a self-reported value the checker must ignore
            (out / "decision.json").write_text(json.dumps(d), encoding="utf-8")
            (out / "summary.txt").write_text(
                "Settings: iterations=10, d=4, seed=1, Tp=0.4, safety time cap=600 s\n"
                "Stopping rule: iteration count reached; iterations run: 10\n"
                "Computation time (s): 0.5000\n", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "check":  # the real checker
            return subprocess.run([sys.executable, "-m", "flowshop.checker", *args[1:]],
                                  capture_output=True, text=True, encoding="utf-8")
        raise AssertionError(args)

    monkeypatch.setattr(compare, "pixi", fake_pixi)
    row, report = compare.run_one("bad", "hand_checkable", DATA, tmp_path, "test cpu")
    assert row["feasible"] is False
    assert row["total_weighted_tardiness"] == row["total_waiting"] == row["makespan"] == ""
    assert row["runtime_s"] == 0.5
    assert row["time_limit_s"] == 600.0
    assert row["stopping_rule"] == "iteration count reached; iterations run: 10"
    assert "infeasible" in row["note"]
    assert report["feasible"] is False


def test_gantt_bars_come_from_the_report():
    report = {
        "stages": ["A", "B"],
        "sequence": ["J2", "J1"],
        "measures": {"total_weighted_tardiness": 1, "total_waiting": 2, "makespan": 30},
        "operations": [
            {"job_id": "J2", "stage_id": "A", "start": 0, "completion": 5},
            {"job_id": "J2", "stage_id": "B", "start": 5, "completion": 12.5},
            {"job_id": "J1", "stage_id": "A", "start": 5, "completion": 20},
            {"job_id": "J1", "stage_id": "B", "start": 20, "completion": 30},
        ],
    }
    fig, ax = plots.gantt(report, "test")
    bars = sorted((round(p.get_x(), 9), round(p.get_width(), 9)) for p in ax.patches)
    assert bars == [(0, 5), (5, 7.5), (5, 15), (20, 10)]
    # A job keeps one color at every stage.
    colors = plots.job_colors(report["sequence"])
    assert colors["J2"] == plots.CATEGORICAL[0] and colors["J1"] == plots.CATEGORICAL[1]
    plots.plt.close(fig)


def test_job_colors_use_ordinal_ramp_past_eight_jobs():
    seq = [f"J{i:03d}" for i in range(1, 16)]
    colors = plots.job_colors(seq)
    assert len(set(colors.values())) == 15
    assert colors["J001"].lower() == plots.ORDINAL_BLUE[0] and colors["J015"].lower() == plots.ORDINAL_BLUE[-1]


def test_crashed_check_never_reuses_an_old_report(tmp_path, monkeypatch):
    out = tmp_path / "runs" / "rule" / "hand_checkable"
    out.mkdir(parents=True)
    (out / "check_report.json").write_text(json.dumps(
        {"feasible": True, "violations": [], "measures": {"total_weighted_tardiness": 1,
         "total_waiting": 1, "makespan": 1}, "stages": [], "sequence": [], "operations": []}), encoding="utf-8")

    def fake_pixi(*args):
        if args[0] == "solve":
            shutil.copy(SOLUTION, out / "decision.json")
            (out / "summary.txt").write_text("Computation time (s): 0.1\n", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "Traceback ... crash")  # writes no report

    monkeypatch.setattr(compare, "pixi", fake_pixi)
    row, report = compare.run_one("rule", "hand_checkable", DATA, tmp_path, "cpu")
    assert report is None
    assert row["feasible"] is False and row["total_weighted_tardiness"] == ""
    assert "check exited 1" in row["note"]


@pytest.mark.parametrize("value, text", [(281, "281"), (23015.0, "23,015"), (1234567, "1,234,567"),
                                          (2371.0004, "2,371.0004"), (0.1 + 0.2, "0.3")])
def test_measure_labels_are_not_rounded_to_hide_differences(value, text):
    assert plots.fmt(value) == text
