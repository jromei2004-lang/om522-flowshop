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

Resumable: if the output file already has every requested iteration row for an
(instance, d, Tp, seed), that run is skipped, so a stopped grid picks up where it left
off. Rows of unfinished runs and any half-written last line are dropped first. Results
are deterministic, so a resumed grid gives the same rows as an uninterrupted one
(runtimes aside). Use --fresh to start over.

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


def run_key(instance: str, d, tp, seed) -> tuple:
    return (instance, int(d), float(tp), int(seed))


def load_finished(path: Path, checkpoints: list[int], grid_keys: set[tuple]) -> tuple[list[dict], set[tuple]]:
    """Read an existing results file. Returns the rows to keep and the keys of runs
    that already have every requested checkpoint.

    Drops lines that are cut off or unreadable, and rows of runs in this grid that do
    not have every checkpoint (those runs are redone). Rows of runs outside this grid
    are kept as they are.
    """
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise SystemExit(
                f"{path} has different columns than this version of tune. "
                "Use --out with a new file, or --fresh to start over."
            )
        rows = []
        for row in reader:
            if None in row or any(row[c] in (None, "") for c in COLUMNS if c != "gap_pct"):
                continue  # half-written or damaged line
            try:
                key = run_key(row["instance"], row["d"], row["tp"], row["seed"])
                int(row["iterations"])
                float(row["twt"])
            except ValueError:
                continue
            rows.append(row)

    have: dict[tuple, set[int]] = {}
    for row in rows:
        have.setdefault(run_key(row["instance"], row["d"], row["tp"], row["seed"]), set()).add(
            int(row["iterations"])
        )
    finished = {key for key, its in have.items() if set(checkpoints) <= its}
    kept = [
        r for r in rows
        if (key := run_key(r["instance"], r["d"], r["tp"], r["seed"])) in finished or key not in grid_keys
    ]
    return kept, finished


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tune", description="Iterated Greedy tuning grid")
    parser.add_argument("--instances", nargs="+", default=list(ALLOWED_INSTANCES), choices=ALLOWED_INSTANCES)
    parser.add_argument("--d", nargs="+", type=int, default=[2, 4, 6, 8])
    parser.add_argument("--iterations", nargs="+", type=int, default=[500, 1000, 2000])
    parser.add_argument("--tp", nargs="+", type=float, default=[0.2, 0.4, 0.8])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "tuning.csv")
    parser.add_argument("--fresh", action="store_true", help="ignore existing results and start over")
    args = parser.parse_args(argv)

    checkpoints = sorted(set(args.iterations))
    grid = [(name, d, tp, seed) for name in args.instances for d in args.d for tp in args.tp for seed in args.seeds]

    kept, finished = [], set()
    if args.out.is_file() and not args.fresh:
        kept, finished = load_finished(args.out, checkpoints, {run_key(*g) for g in grid})
    todo = [g for g in grid if run_key(*g) not in finished]
    print(f"{len(grid)} runs in grid, {len(grid) - len(todo)} already done, {len(todo)} to run "
          f"(each to {checkpoints[-1]} iterations, recorded at {checkpoints}) -> {args.out}")

    # Rewrite the file with only clean rows, then append new runs to it. Written to a
    # temporary file first so an interruption here cannot damage the existing results.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_name(args.out.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
    tmp.replace(args.out)
    if not todo:
        print("Nothing to run.")
        return 0

    # Compile numba (or load its cache) before timing anything.
    iterated_greedy.solve(load_instance(DATA / "hand_checkable"), iterated_greedy.Settings(iterations=1))

    grid_start = time.perf_counter()
    instances, rule_twts = {}, {}
    with args.out.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        for done, (name, d, tp, seed) in enumerate(todo, start=1):
            if name not in instances:
                instances[name] = load_instance(DATA / name)
                _, rule_times = rule_to_beat.solve(instances[name])
                rule_twts[name] = total_weighted_tardiness(instances[name], rule_times)
            instance, rule_twt = instances[name], rule_twts[name]

            settings = iterated_greedy.Settings(iterations=checkpoints[-1], d=d, seed=seed, tp=tp)
            result = iterated_greedy.solve(instance, settings, checkpoints=checkpoints)
            rows = []
            for it in checkpoints:
                cp = result.checkpoints[it]
                times = build_schedule(instance, cp.sequence)
                twt = total_weighted_tardiness(instance, times)
                rows.append({
                    "instance": name, "jobs": len(instance.jobs), "d": d, "iterations": it,
                    "tp": tp, "seed": seed, "twt": twt, "rule_twt": rule_twt,
                    "gap_pct": gap_pct(rule_twt, twt), "waiting": total_waiting(instance, times),
                    "runtime_s": f"{cp.elapsed:.4f}", "stop_reason": cp.stop_reason,
                    "checker": "pending", "sequence": " ".join(cp.sequence),
                })
            writer.writerows(rows)  # all rows of a run together, then flush
            f.flush()

            elapsed = time.perf_counter() - grid_start
            eta = elapsed / done * (len(todo) - done)
            final = result.checkpoints[checkpoints[-1]]
            print(f"[{done}/{len(todo)}] {name} d={d} tp={tp} seed={seed}: "
                  f"TWT {result.twt:g} (rule {rule_twt:g}) in {final.elapsed:.1f} s; "
                  f"ETA {eta / 60:.1f} min", flush=True)
    print(f"Done in {(time.perf_counter() - grid_start) / 60:.1f} min. Results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
