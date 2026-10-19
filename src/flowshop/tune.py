"""Tuning grid for Iterated Greedy: pixi run tune [options].

Default grid, on the three development instances only (never the held-out case):
  d (jobs removed per iteration): 2, 4, 6, 8
  iterations:                     500, 1000, 2000
  Tp (temperature factor):        0.2, 0.4, 0.8
  seeds:                          1, 2, 3, 4, 5

Iteration counts share one run. With the same seed and settings, the first 500
iterations of a 2000-iteration run are exactly a 500-iteration run (same random
numbers, same steps), so each run records its best sequence at 500, 1000, and 2000
iterations. tests/test_tune.py checks this equivalence.

Each row of results/tuning.csv is one (instance, d, iterations, Tp, seed). Weighted
tardiness and waiting are recomputed with schedule.py from the recorded sequence.
runtime_s is the time from the start of solve to that checkpoint; numba is compiled
once before the grid starts, so no row includes compile time.

The `checker` column says whether the independent checker confirmed the decision. The
checker is being built on a separate branch, so it reads "pending" until it is merged;
the `sequence` column holds enough to rebuild and check every decision then.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from flowshop import iterated_greedy, rule_to_beat
from flowshop.loader import load_instance
from flowshop.schedule import build_schedule, total_waiting, total_weighted_tardiness

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ALLOWED_INSTANCES = ("development_small", "development_medium", "development_large")

COLUMNS = [
    "instance", "jobs", "d", "iterations", "tp", "seed",
    "twt", "rule_twt", "gap_pct", "waiting", "runtime_s", "stop_reason", "checker", "sequence",
]


def gap_pct(rule_twt: float, twt: float) -> str:
    """Percent reduction versus the rule to beat; blank when the rule's TWT is 0."""
    if rule_twt == 0:
        return ""
    return f"{(rule_twt - twt) / rule_twt * 100:.4f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tune", description="Iterated Greedy tuning grid")
    parser.add_argument("--instances", nargs="+", default=list(ALLOWED_INSTANCES), choices=ALLOWED_INSTANCES)
    parser.add_argument("--d", nargs="+", type=int, default=[2, 4, 6, 8])
    parser.add_argument("--iterations", nargs="+", type=int, default=[500, 1000, 2000])
    parser.add_argument("--tp", nargs="+", type=float, default=[0.2, 0.4, 0.8])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "tuning.csv")
    args = parser.parse_args(argv)

    checkpoints = sorted(set(args.iterations))
    total_runs = len(args.instances) * len(args.d) * len(args.tp) * len(args.seeds)
    print(f"{total_runs} runs (each to {checkpoints[-1]} iterations, recorded at {checkpoints}) -> {args.out}")

    # Compile numba (or load its cache) before timing anything.
    iterated_greedy.solve(load_instance(DATA / "hand_checkable"), iterated_greedy.Settings(iterations=1))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    grid_start = time.perf_counter()
    done = 0
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for name in args.instances:
            instance = load_instance(DATA / name)
            _, rule_times = rule_to_beat.solve(instance)
            rule_twt = total_weighted_tardiness(instance, rule_times)
            for d in args.d:
                for tp in args.tp:
                    for seed in args.seeds:
                        settings = iterated_greedy.Settings(iterations=checkpoints[-1], d=d, seed=seed, tp=tp)
                        result = iterated_greedy.solve(instance, settings, checkpoints=checkpoints)
                        for it in checkpoints:
                            cp = result.checkpoints[it]
                            times = build_schedule(instance, cp.sequence)
                            twt = total_weighted_tardiness(instance, times)
                            writer.writerow({
                                "instance": name, "jobs": len(instance.jobs), "d": d, "iterations": it,
                                "tp": tp, "seed": seed, "twt": twt, "rule_twt": rule_twt,
                                "gap_pct": gap_pct(rule_twt, twt), "waiting": total_waiting(instance, times),
                                "runtime_s": f"{cp.elapsed:.4f}", "stop_reason": cp.stop_reason,
                                "checker": "pending", "sequence": " ".join(cp.sequence),
                            })
                        f.flush()
                        done += 1
                        elapsed = time.perf_counter() - grid_start
                        eta = elapsed / done * (total_runs - done)
                        final = result.checkpoints[checkpoints[-1]]
                        print(f"[{done}/{total_runs}] {name} d={d} tp={tp} seed={seed}: "
                              f"TWT {result.twt:g} (rule {rule_twt:g}) in {final.elapsed:.1f} s; "
                              f"ETA {eta / 60:.1f} min", flush=True)
    print(f"Done in {(time.perf_counter() - grid_start) / 60:.1f} min. Results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
