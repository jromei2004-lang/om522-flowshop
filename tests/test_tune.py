"""Tests for the tuning grid and the iteration checkpoints it relies on."""

import csv
from pathlib import Path

import pytest

from flowshop import iterated_greedy, tune
from flowshop.iterated_greedy import Settings
from flowshop.loader import load_instance

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.mark.parametrize("name", ["development_small", "development_medium"])
def test_checkpoint_equals_separate_shorter_run(name):
    """Best sequence at iteration k of a long run == result of a k-iteration run."""
    instance = load_instance(DATA / name)
    long_run = iterated_greedy.solve(instance, Settings(iterations=40, d=4, seed=3), checkpoints=[10, 25, 40])
    for k in (10, 25, 40):
        short = iterated_greedy.solve(instance, Settings(iterations=k, d=4, seed=3))
        assert long_run.checkpoints[k].sequence == short.sequence
        assert long_run.checkpoints[k].iterations_done == short.iterations_done == k


def test_tune_writes_one_row_per_run(tmp_path):
    out = tmp_path / "tuning.csv"
    assert tune.main([
        "--instances", "development_small", "--d", "2", "4", "--iterations", "5", "10",
        "--tp", "0.4", "--seeds", "1", "2", "--out", str(out),
    ]) == 0
    with out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2 * 2 * 2  # d values x iteration counts x seeds
    assert set(rows[0]) == set(tune.COLUMNS)
    for row in rows:
        assert float(row["twt"]) <= float(row["rule_twt"])
        assert row["rule_twt"] == "1417"
        assert row["checker"] == "pending"


SMALL_GRID = ["--instances", "development_small", "--d", "2", "--iterations", "5", "10", "--tp", "0.4"]


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def without_runtime(rows):
    return sorted(tuple((k, v) for k, v in r.items() if k != "runtime_s") for r in rows)


def test_resume_skips_finished_runs(tmp_path, capsys):
    out = tmp_path / "tuning.csv"
    tune.main(SMALL_GRID + ["--seeds", "1", "--out", str(out)])
    first = read_rows(out)
    capsys.readouterr()

    tune.main(SMALL_GRID + ["--seeds", "1", "2", "--out", str(out)])
    assert "2 runs in grid, 1 already done, 1 to run" in capsys.readouterr().out
    resumed = read_rows(out)
    assert resumed[:2] == first  # seed 1 rows untouched (same runtimes, so not rerun)
    assert len(resumed) == 4

    # Same results as one uninterrupted run, apart from runtimes.
    fresh = tmp_path / "fresh.csv"
    tune.main(SMALL_GRID + ["--seeds", "1", "2", "--out", str(fresh)])
    assert without_runtime(resumed) == without_runtime(read_rows(fresh))


def test_resume_cleans_partial_run_and_cut_off_line(tmp_path, capsys):
    out = tmp_path / "tuning.csv"
    tune.main(SMALL_GRID + ["--seeds", "1", "2", "--out", str(out)])
    lines = out.read_text(encoding="utf-8").splitlines()
    # Keep seed 1 complete, only the first row of seed 2, then half of a line.
    damaged = lines[:3] + [lines[3]] + [lines[4][:20]]
    out.write_text("\n".join(damaged), encoding="utf-8")
    capsys.readouterr()

    tune.main(SMALL_GRID + ["--seeds", "1", "2", "--out", str(out)])
    assert "1 already done, 1 to run" in capsys.readouterr().out
    rows = read_rows(out)
    keys = [(r["seed"], r["iterations"]) for r in rows]
    assert sorted(keys) == [("1", "10"), ("1", "5"), ("2", "10"), ("2", "5")]  # no duplicates


def test_resume_refuses_file_with_other_columns(tmp_path):
    out = tmp_path / "tuning.csv"
    out.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        tune.main(SMALL_GRID + ["--seeds", "1", "--out", str(out)])


def test_tune_refuses_other_instances(tmp_path):
    with pytest.raises(SystemExit):
        tune.main(["--instances", "hand_checkable", "--out", str(tmp_path / "x.csv")])
