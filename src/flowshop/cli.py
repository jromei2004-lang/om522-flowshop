"""Command line entry point: pixi run solve <input_dir> <output_dir>.

For now it only loads and checks the input. The methods are not built yet, so it
never writes decision.json.

Exit status: 1 for malformed input (message names the file and column), 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flowshop.loader import InputError, load_instance

MAX_PROBLEMS_SHOWN = 50


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solve", description="Option 6 flow shop decision tool")
    parser.add_argument("input_dir", type=Path, help="instance directory (left unchanged)")
    parser.add_argument("output_dir", type=Path, help="directory for decision.json and the summary")
    args = parser.parse_args(argv)

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

    print(
        f"Input OK: {len(instance.jobs)} jobs, {len(instance.stages)} stages. "
        "Methods are not built yet, so no decision.json was written."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
