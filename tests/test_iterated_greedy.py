"""Tests for method 2, Iterated Greedy.

Short iteration counts keep the suite fast; the default settings are exercised by
`pixi run solve` and later by `pixi run tune`.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from flowshop import iterated_greedy, rule_to_beat
from flowshop.cli import main
from flowshop.iterated_greedy import Settings
from flowshop.loader import load_instance
from flowshop.schedule import build_schedule, total_weighted_tardiness

DATA = Path(__file__).resolve().parent.parent / "data"
DEV = ["development_small", "development_medium", "development_large"]


def rule_twt(instance):
    _, times = rule_to_beat.solve(instance)
    return total_weighted_tardiness(instance, times)


@pytest.mark.parametrize("name", ["hand_checkable"] + DEV)
def test_never_worse_than_rule_and_consistent(name):
    instance = load_instance(DATA / name)
    result = iterated_greedy.solve(instance, Settings(iterations=20))
    assert result.edd_twt == rule_twt(instance)
    assert result.twt <= result.edd_twt
    # Reported times and measure come from schedule.py for the returned sequence.
    assert sorted(result.sequence) == sorted(instance.jobs)
    assert result.times == build_schedule(instance, result.sequence)
    assert result.twt == total_weighted_tardiness(instance, result.times)


def test_hand_checkable_at_most_281():
    result = iterated_greedy.solve(load_instance(DATA / "hand_checkable"), Settings(iterations=50))
    assert result.twt <= 281


def test_same_seed_same_decision():
    instance = load_instance(DATA / "development_medium")
    a = iterated_greedy.solve(instance, Settings(iterations=30, seed=7))
    b = iterated_greedy.solve(instance, Settings(iterations=30, seed=7))
    assert a.sequence == b.sequence
    assert a.times == b.times


def test_stops_on_iteration_count():
    result = iterated_greedy.solve(load_instance(DATA / "development_small"), Settings(iterations=25))
    assert result.iterations_done == 25
    assert result.stop_reason.startswith("iteration count")


def test_safety_cap_is_reported():
    result = iterated_greedy.solve(
        load_instance(DATA / "development_small"), Settings(iterations=10_000, time_limit=0.0)
    )
    assert result.iterations_done == 0
    assert "SAFETY TIME CAP" in result.stop_reason


def keep_jobs(tmp_path, job_ids):
    """Copy hand_checkable keeping only the listed jobs (and their processing times)."""
    inst = tmp_path / "subset"
    shutil.copytree(DATA / "hand_checkable", inst)
    for name in ["jobs.csv", "processing_times.csv"]:
        path = inst / name
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = [lines[0]] + [ln for ln in lines[1:] if ln.split(",")[0] in job_ids]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return load_instance(inst)


def test_one_job(tmp_path):
    result = iterated_greedy.solve(keep_jobs(tmp_path, {"J003"}), Settings(iterations=10))
    assert result.sequence == ["J003"]
    assert result.iterations_done == 0
    assert result.stop_reason.startswith("no search needed")


def test_zero_jobs(tmp_path):
    result = iterated_greedy.solve(keep_jobs(tmp_path, set()), Settings(iterations=10))
    assert result.sequence == []
    assert result.twt == 0


def test_d_larger_than_job_count():
    instance = load_instance(DATA / "hand_checkable")
    result = iterated_greedy.solve(instance, Settings(iterations=20, d=10))
    assert result.d_used == 6
    assert result.iterations_done == 20
    assert result.twt <= 281


def test_same_result_in_separate_processes(tmp_path):
    """Two fresh processes (as on a rerun) write byte-identical decision.json files."""
    outputs = []
    for run in ("a", "b"):
        out = tmp_path / run
        result = subprocess.run(
            [sys.executable, "-m", "flowshop.cli", str(DATA / "development_small"), str(out),
             "--iterations", "30"],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        outputs.append((out / "decision.json").read_bytes())
    assert outputs[0] == outputs[1]


def test_solve_command_defaults_to_ig(tmp_path):
    out = tmp_path / "out"
    assert main([str(DATA / "hand_checkable"), str(out), "--iterations", "10"]) == 0
    summary = (out / "summary.txt").read_text(encoding="utf-8")
    assert "Iterated Greedy" in summary
    with (out / "decision.json").open(encoding="utf-8") as f:
        decision = json.load(f)
    assert set(decision) == {"sequence", "schedule"}
    assert len(decision["schedule"]) == 6 * 4
