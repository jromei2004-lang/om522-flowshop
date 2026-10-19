"""Command line entry point: pixi run solve <input_dir> <output_dir> [--method ig|rule].

Loads and checks the input, runs a method, and writes decision.json plus summary.txt
to the output directory. The default method is Iterated Greedy (the researched method)
with fixed default settings, so a rerun reproduces the same decision.

Exit status: 1 for malformed input (message names the file and column, no
decision.json), 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from flowshop import iterated_greedy, rule_to_beat
from flowshop.decision import build_decision, write_decision
from flowshop.loader import InputError, Instance, load_instance
from flowshop.schedule import total_waiting, total_weighted_tardiness

MAX_PROBLEMS_SHOWN = 50
DEFAULT_METHOD = "ig"


def run_rule(instance: Instance, args) -> tuple[list[str], dict, list[str]]:
    sequence, times = rule_to_beat.solve(instance)
    return sequence, times, ["Method: Rule to beat (earliest due date, ties by job id)",
                             "Stopping rule: single construction pass (no search)"]


def run_ig(instance: Instance, args) -> tuple[list[str], dict, list[str]]:
    # numba compiles (or loads its cached compiled code) on the first call inside
    # solve, so the reported computation time includes it.
    settings = iterated_greedy.Settings(
        iterations=args.iterations, d=args.d, seed=args.seed, tp=args.tp, time_limit=args.time_limit
    )
    result = iterated_greedy.solve(instance, settings)
    lines = [
        "Method: Iterated Greedy (Ruiz and Stützle 2007) with NEH-style insertion, from EDD",
        f"Settings: iterations={settings.iterations}, d={result.d_used}, seed={settings.seed}, "
        f"Tp={settings.tp}, safety time cap={settings.time_limit:.0f} s",
        f"Stopping rule: {result.stop_reason}; iterations run: {result.iterations_done}",
        f"Rule to beat (EDD) weighted tardiness: {result.edd_twt:g}",
        f"After NEH and local search: {result.start_twt:g}",
    ]
    return result.sequence, result.times, lines


METHODS = {"ig": run_ig, "rule": run_rule}


def main(argv: list[str] | None = None) -> int:
    defaults = iterated_greedy.Settings()
    parser = argparse.ArgumentParser(prog="solve", description="Option 6 flow shop decision tool")
    parser.add_argument("input_dir", type=Path, help="instance directory (left unchanged)")
    parser.add_argument("output_dir", type=Path, help="directory for decision.json and summary.txt")
    parser.add_argument("--method", choices=sorted(METHODS), default=DEFAULT_METHOD)
    parser.add_argument("--iterations", type=int, default=defaults.iterations)
    parser.add_argument("--d", type=int, default=defaults.d, help="jobs removed per iteration")
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--tp", type=float, default=defaults.tp, help="temperature factor")
    parser.add_argument("--time-limit", type=float, default=defaults.time_limit,
                        help="safety cap in seconds (iteration count is the stopping rule)")
    args = parser.parse_args(argv)
    if args.iterations < 0 or args.d < 1 or args.tp < 0 or args.time_limit <= 0:
        parser.error("need iterations >= 0, d >= 1, tp >= 0, and time-limit > 0")

    if args.output_dir.resolve() == args.input_dir.resolve():
        print("Output directory must be different from the input directory.", file=sys.stderr)
        return 1

    # Remove a decision.json left by an earlier run, so a rejected input never leaves
    # an old result in the output directory that could be mistaken for a new one.
    stale = args.output_dir / "decision.json"
    if stale.is_file():
        stale.unlink()
        print(f"Removed old {stale} from a previous run.")

    try:
        instance = load_instance(args.input_dir)
    except InputError as err:
        print(f"Input rejected: {args.input_dir}", file=sys.stderr)
        for problem in err.problems[:MAX_PROBLEMS_SHOWN]:
            print(f"  - {problem}", file=sys.stderr)
        hidden = len(err.problems) - MAX_PROBLEMS_SHOWN
        if hidden > 0:
            print(f"  ... and {hidden} more problems", file=sys.stderr)
        print("No decision.json was written.", file=sys.stderr)
        return 1

    started = time.perf_counter()
    try:
        sequence, times, method_lines = METHODS[args.method](instance, args)
    except iterated_greedy.EvaluationMismatch as err:
        # Internal safety check failed: refuse to write a decision we cannot vouch for.
        print(f"Internal error, no decision.json written: {err}", file=sys.stderr)
        return 2
    runtime = time.perf_counter() - started

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_decision(args.output_dir / "decision.json", build_decision(instance, sequence, times))

    summary = "\n".join(method_lines + [
        "Status: feasible decision written to decision.json",
        f"Instance: {args.input_dir} ({len(instance.jobs)} jobs, {len(instance.stages)} stages)",
        f"Total weighted tardiness: {total_weighted_tardiness(instance, times)}",
        f"Total waiting between stages: {total_waiting(instance, times)}",
        f"Computation time (s): {runtime:.4f} (includes numba load and compile for ig)",
        "Measures above are the method's own values. Confirm them with the independent checker.",
    ])
    (args.output_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
