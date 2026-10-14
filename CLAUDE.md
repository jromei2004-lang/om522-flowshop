# OM 522 Team Project: Option 6 (Permutation Flow Shop)

## What this repo is
A decision tool that chooses one job sequence for an eight-stage production line
(permutation flow shop with release dates, minimizing total weighted tardiness).
Two methods: the option's rule to beat, and a researched method (Iterated Greedy,
Ruiz and Stützle 2007, EJOR). Full requirements are in `docs/` (project guide and
option 6 brief). Read them before making design decisions. When anything here
conflicts with the docs, the docs win.

## Non-negotiable rules
- The rule to beat is implemented EXACTLY as the option 6 brief states, including
  tie-breaking. Test 1 must reproduce `worked-example/solution.json` exactly.
- Do NOT use any package that already solves flow shop scheduling as a method.
  General solvers (HiGHS, OR-Tools CP-SAT) are allowed only on a model we formulate.
- In-class notebook code may be reused ONLY for loading or plotting, with
  attribution in the README.
- Never round start or completion times. The instructor's checker requires every
  duration to match the input within 1e-8.
- Default settings use a fixed seed and stop on an iteration count. The time limit
  is only a safety cap. A rerun must reproduce submitted results exactly.
- The whole solve command must finish in under 10 minutes on a size 60 instance.
- Never modify input files. Write results to a separate output directory.

## Entry points (Pixi tasks)
- `pixi run solve <input_dir> <output_dir>` runs the researched method with default
  settings and writes `decision.json` plus a short summary.
- `pixi run test` runs all tests.
- `pixi run compare` regenerates every comparison table and plot.

## Required behavior on input
Before solving, check: every required file and column is present, values have
their declared types (see schema.json), every referenced identifier exists, and
processing times are positive.
- Malformed input: print a message naming the file and column, write NO
  decision.json, exit with nonzero status.
- Valid input with nothing feasible: print "no feasible decision found", write NO
  decision.json, exit with status zero.
- Otherwise: write decision.json (same structure as worked-example/solution.json)
  and exit with status zero.
- Never silently replace missing or invalid values.

## Checker
`checker` is independent of both methods. It reads only the input files and a
decision.json, recomputes every start, completion, and measure from scratch, and
reports which jobs violate which constraint. Never import method code into the
checker. A better measure never makes up for an infeasible decision.

## Required tests
1. Rule to beat reproduces the worked example's decision and measures.
2. The supplied edge case is rejected as the brief specifies.
3. A copied instance with a required column deleted is rejected with a clear message.

## Cross-platform (one teammate on Windows, one on Mac)
- pixi.toml must list platforms = ["win-64", "osx-arm64", "osx-64"] so the lock
  file works on both machines.
- Build every file path with pathlib. Never hardcode backslashes or forward slashes.
- Read and write CSV and JSON with explicit encoding="utf-8".
- Keep a .gitattributes with `* text=auto` so line endings don't cause fake diffs.
- Pixi tasks must run identically in PowerShell and the Mac terminal (call Python
  scripts, not shell-specific commands).

## Repo hygiene
- No secrets, personal data, caches, or absolute machine-specific paths.
- Commit pixi.toml and pixi.lock.
- Work on branches and keep main passing tests.
- When you (the agent) make a mistake that we catch, remind us to log it in
  `agent_log.md`.
