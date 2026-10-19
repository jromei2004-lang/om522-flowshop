"""Tests for method 1, the rule to beat (earliest due date, ties by job id).

Required test 1: the rule reproduces worked-example/solution.json and its measures.
"""

import json
import shutil
from pathlib import Path

from flowshop import rule_to_beat
from flowshop.cli import main
from flowshop.loader import load_instance
from flowshop.schedule import total_waiting, total_weighted_tardiness

DATA = Path(__file__).resolve().parent.parent / "data"
WORKED = DATA / "worked-example"


def read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def copy_instance(name: str, tmp_path: Path) -> Path:
    target = tmp_path / name
    shutil.copytree(DATA / name, target)
    return target


def set_due_date(instance_dir: Path, job_id: str, due: str) -> None:
    path = instance_dir / "jobs.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        parts = line.split(",")
        if parts[0] == job_id:
            parts[2] = due
            lines[i] = ",".join(parts)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- Required test 1: reproduce the worked example ----------

def test_rule_reproduces_worked_example(tmp_path):
    expected = read_json(WORKED / "solution.json")
    metrics = read_json(WORKED / "metrics.json")

    # Run the real solve command so this also covers writing decision.json.
    out = tmp_path / "out"
    assert main([str(DATA / "hand_checkable"), str(out), "--method", "rule"]) == 0
    decision = read_json(out / "decision.json")

    assert decision["sequence"] == expected["sequence"]
    assert len(decision["schedule"]) == len(expected["schedule"]) == 24

    ours = {(e["job_id"], e["stage_id"]): (e["start"], e["completion"]) for e in decision["schedule"]}
    theirs = {(e["job_id"], e["stage_id"]): (e["start"], e["completion"]) for e in expected["schedule"]}
    assert ours.keys() == theirs.keys()
    for key in theirs:
        assert ours[key] == theirs[key], f"{key}: ours {ours[key]}, worked example {theirs[key]}"

    # Same structure and order as solution.json, entry for entry.
    assert decision == expected

    instance = load_instance(DATA / "hand_checkable")
    sequence, times = rule_to_beat.solve(instance)
    twt = total_weighted_tardiness(instance, times)
    waiting = total_waiting(instance, times)
    assert twt == 281
    assert waiting == 13
    assert abs(twt - metrics["total_weighted_tardiness"]) < 1e-9
    assert abs(waiting - metrics["downstream_waiting_time"]) < 1e-9


# ---------- Rule details ----------

def test_ties_broken_by_job_id(tmp_path):
    # Give J005 the same due date as J001 (43). J001 has the smaller id, so it goes first.
    inst = copy_instance("hand_checkable", tmp_path)
    set_due_date(inst, "J005", "43")
    assert rule_to_beat.edd_sequence(load_instance(inst))[:2] == ["J001", "J005"]

    # Now make J001 tie with J002 (45). J001 still goes before J002.
    set_due_date(inst, "J001", "45")
    set_due_date(inst, "J005", "67")
    assert rule_to_beat.edd_sequence(load_instance(inst))[:2] == ["J001", "J002"]


def test_tie_break_does_not_depend_on_row_order(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    set_due_date(inst, "J005", "43")
    path = inst / "jobs.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0]] + lines[1:][::-1]) + "\n", encoding="utf-8")
    assert rule_to_beat.edd_sequence(load_instance(inst))[:2] == ["J001", "J005"]


def test_eight_stage_instance_uses_stages_csv():
    instance = load_instance(DATA / "development_small")
    sequence, times = rule_to_beat.solve(instance)
    assert len(instance.stages) == 8
    assert len(times) == 15 * 8
    # Same sequence at every stage: start times rise along the sequence on each stage.
    for stage in instance.stages:
        starts = [times[(j, stage)][0] for j in sequence]
        assert starts == sorted(starts)


def test_schedule_follows_start_rule_on_all_dev_instances():
    for name in ["development_small", "development_medium", "development_large"]:
        instance = load_instance(DATA / name)
        sequence, times = rule_to_beat.solve(instance)
        for i, job_id in enumerate(sequence):
            for k, stage in enumerate(instance.stages):
                start, completion = times[(job_id, stage)]
                ready = instance.jobs[job_id].release_time if k == 0 else times[(job_id, instance.stages[k - 1])][1]
                free = times[(sequence[i - 1], stage)][1] if i > 0 else ready
                assert start == max(ready, free)
                assert completion - start == instance.processing_time[(job_id, stage)]


def test_decimal_times_not_rounded(tmp_path):
    inst = copy_instance("hand_checkable", tmp_path)
    schema = (inst / "schema.json").read_text(encoding="utf-8")
    schema = schema.replace(
        '"name": "processing_time",\n          "type": "integer"',
        '"name": "processing_time",\n          "type": "number"',
    )
    (inst / "schema.json").write_text(schema, encoding="utf-8")
    path = inst / "processing_times.csv"
    text = path.read_text(encoding="utf-8").replace("J001,S1,11", "J001,S1,11.123456789")
    path.write_text(text, encoding="utf-8")

    out = tmp_path / "out"
    assert main([str(inst), str(out), "--method", "rule"]) == 0
    decision = read_json(out / "decision.json")
    first = decision["schedule"][0]
    assert (first["job_id"], first["stage_id"]) == ("J001", "S1")
    assert first["completion"] == 13 + 11.123456789
    assert abs((first["completion"] - first["start"]) - 11.123456789) < 1e-8
