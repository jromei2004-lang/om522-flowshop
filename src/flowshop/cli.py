"""Command line entry point: pixi run solve <input_dir> <output_dir> [--method rule].

Loads and checks the input, runs a method, and writes decision.json plus summary.txt
to the output directory.

Exit status: 1 for malformed input (message names the file and column, no
decision.json), 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from flowshop import rule_to_beat
from flowshop.decision import build_decision, write_decision
from flowshop.loader import InputError, load_instance
from flowshop.schedule import total_waiting, total_weighted_tardiness

MAX_PROBLEMS_SHOWN = 50

# Only the rule to beat exists so far. When Iterated Greedy is added it becomes the
# default, because the instructor's solve command must run the researched method.
METHODS = {"rule": ("Rule to beat (earliest due date, ties by job id)", rule_to_beat.solve)}
DEFAULT_METHOD = "rule"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solve", description="Option 6 flow shop decision tool")
    parser.add_argument("input_dir", type=Path, help="instance directory (left unchanged)")
    parser.add_argument("output_dir", type=Path, help="directory for decision.json and summary.txt")
    parser.add_argument("--method", choices=sorted(METHODS), default=DEFAULT_METHOD)
    args = parser.parse_args(argv)

    # Results never go inside the input directory, so input files stay untouched.
    if args.output_dir.resolve().is_relative_to(args.input_dir.resolve()):
        print("Output directory must not be the input directory or inside it.", file=sys.stderr)
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

    method_name, solve = METHODS[args.method]
    started = time.perf_counter()
    sequence, times = solve(instance)
    runtime = time.perf_counter() - started

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_decision(args.output_dir / "decision.json", build_decision(instance, sequence, times))

    summary = "\n".join([
        f"Method: {method_name}",
        "Status: feasible decision written to decision.json",
        f"Instance: {args.input_dir} ({len(instance.jobs)} jobs, {len(instance.stages)} stages)",
        f"Total weighted tardiness: {total_weighted_tardiness(instance, times)}",
        f"Total waiting between stages: {total_waiting(instance, times)}",
        f"Computation time (s): {runtime:.4f}",
        "Measures above are the method's own values. Confirm them with the independent checker.",
    ])
    (args.output_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
