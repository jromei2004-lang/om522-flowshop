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


def test_tune_refuses_other_instances(tmp_path):
    with pytest.raises(SystemExit):
        tune.main(["--instances", "hand_checkable", "--out", str(tmp_path / "x.csv")])
