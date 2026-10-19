# Progress log

Newest entry first. See "Session handoff" in CLAUDE.md for when to update this file.

## 2026-10-19 (loader fixes)

### What changed
- Branch `james/loader-fixes`, rebased onto `main` after the checker merge (PR #2). Closes the five open loader findings from the
  first review:
  - Finding 1: a short row names the columns with no value
    (`jobs.csv, column weight, line 3: no value ...`); a long row names the last column.
  - Finding 3: a jobs.csv or stages.csv with a header but no rows is rejected.
  - Finding 4: integer and number patterns use `[0-9]`, not `\d`, which also matched
    non-ASCII digits that int() and float() accept.
  - Finding 5: extra columns declared in schema.json must have a known type.
  - Finding 6: `solve` refuses an output directory inside the input directory (it refused
    only the same directory before).
- One test per fix in tests/test_loader.py (8 new tests). Each fix test fails on the old code.

### Test results
`pixi run test`: 87 passed (79 on main with the checker + 8 new).

### Current best scores
Unchanged (rule to beat): hand_checkable 281, development_small 1417,
development_medium 2371, development_large 23015.

### Next steps
1. Merge james/loader-fixes (PR #3) after John's review. The progress.md conflict with the
   checker entry is already resolved in the rebase (both entries kept).
2. Iterated Greedy with NEH-style insertion, fixed seed, iteration-count stopping; make it the
   solve default and check every decision it writes with `pixi run check`.

## 2026-10-19 (checker)

### What changed
- Branch `james/checker` (from `main` after the rule-to-beat merge).
- `src/flowshop/checker.py`: independent checker. It imports nothing from `flowshop`, not even
  the loader, and reads the CSVs itself with its own stage order taken from the `sequence`
  column. It checks: each input job exactly once in the sequence (unknown or extra jobs
  rejected); each job-stage pair exactly once in the schedule with job_id, stage_id, start and
  completion present and numeric; durations match within 1e-8; release and stage precedence;
  no overlap on a stage; the same order on every stage. It names the job and stage for each
  violation. It ignores any other keys (for example objective values a method reports) and
  recomputes total weighted tardiness, total waiting and makespan from the decision.
  Exit 0 feasible, 1 infeasible, 2 cannot read the input or decision file.
- `pixi run check <input_dir> <decision.json>` task. The README documents solve, check and test.
- `tests/test_checker.py`: the four requested cases plus tolerance boundaries, each
  constraint, malformed decisions, ignored self-reported values, and two independence tests
  (no flowshop import in the source; importing the checker loads no other flowshop module).
- Reviewer subagent findings fixed (see agent_log.md). Not changed: the checker does not
  enforce schema.json integer types on input (the loader does; the checker only needs numbers),
  and `int()` is applied to input numbers only when they are already exact integers, which
  changes no value.
- docs/team-project-guide.pdf in the repo is the October 7 revision. The task mentioned an
  October 14 revision; if one exists, it should be added to docs/ and rechecked.

### Test results
`pixi run test`: 79 passed. Checker runs:
(a) worked example: feasible, TWT 281, waiting 13, makespan 139.
(b) rule on development_small: feasible, TWT 1417 (waiting 732, makespan 417).
(c) J003 at S2 start changed 72 to 73: infeasible, duration violation at J003/S2.
(d) J002 and J005 swapped in the sequence only: infeasible, same-sequence violation at S1 to S4.
The rule's decisions on development_medium and development_large are also feasible.

### Current best scores (rule to beat, now checker-verified)
hand_checkable 281, development_small 1417, development_medium 2371,
development_large 23015 (total weighted tardiness).

### Next steps
1. Merge james/checker into main after review.
2. Loader fixes from the earlier review (see the rule-to-beat entry below).
3. Iterated Greedy with NEH-style insertion; check every decision it writes with
   `pixi run check`.


## 2026-10-19 (rule to beat)

### What changed
- Branch `john/rule-to-beat` (from `loader`). James is building the checker on his own
  branch with his own Claude Code; this branch does not touch the checker.
- `src/flowshop/schedule.py`: method-side timing (start = later of job ready and
  machine free; completion = start + processing time; no rounding) plus total weighted
  tardiness and total waiting. Iterated Greedy will reuse it. The checker must not
  import it.
- `src/flowshop/rule_to_beat.py`: earliest due date order, ties by job id (string order).
- `src/flowshop/decision.py`: writes decision.json in the solution.json structure.
- `src/flowshop/cli.py`: solve now writes decision.json and summary.txt. `--method`
  option with `rule` as the only choice and current default. When Iterated Greedy is
  added, it must become the default.
- Loader test for valid input now confirms decision.json is written (closes reviewer
  finding 2).
- findings.md: rule-to-beat baseline table.

### Test results
`pixi run test`: 33 passed. Required test 1 (`test_rule_reproduces_worked_example`)
matches the sequence and all 24 starts and completions in worked-example/solution.json,
with total weighted tardiness 281 and waiting 13. Tests 2 and 3 pass.

### Current best scores (rule to beat; not yet checker-verified for dev instances)
hand_checkable 281, development_small 1417, development_medium 2371,
development_large 23015 (total weighted tardiness).

### Next steps
1. When James's checker is merged, run it on the rule's decisions for all four instances.
2. Loader fixes from the review on a small branch: name columns for rows with the wrong
   number of values (finding 1), reject zero stages or zero jobs (3), `[0-9]` in the
   integer pattern (4), unknown extra column types (5), block an output folder inside
   the input folder (6).
3. Iterated Greedy with NEH-style insertion, fixed seed, iteration-count stopping;
   make it the solve default. Then `pixi run tune` and the tuner subagent.

## 2026-10-19

### What changed
- Project setup: Pixi environment (Python 3.12, pandas, numpy, matplotlib, pytest) for
  win-64, osx-arm64, and osx-64, with pixi.lock committed. `.gitattributes` with
  `* text=auto`. Empty `agent_log.md` and `findings.md`.
- Loader (`src/flowshop/loader.py`): runs the four input checks from the guide (files
  and columns present, schema.json types and non-empty values, referenced ids exist,
  positive processing times), plus structural checks (unique ids, one time per
  job-stage pair, stage sequence 1..n). Reports every problem at once, each naming the
  file and column. Values are read as text first and never rounded or filled in.
- Solve command (`pixi run solve <input_dir> <output_dir>`, `src/flowshop/cli.py`):
  deletes a stale decision.json in the output folder, runs the loader, exits 1 on
  malformed input with no decision.json. On valid input it prints "Input OK" and
  writes nothing yet, because no method exists.
- CLAUDE.md: added Option 6 specifics, Agents, and Session handoff sections.
- Subagents in `.claude/agents/`: `reviewer` (read-only review against the docs) and
  `tuner` (runs and analyzes `pixi run tune`; stops if the task does not exist).
- `compare` and `plot` Pixi tasks are still placeholders. A visuals module is planned
  (Gantt per stage, per-job weighted tardiness bars, method comparison) and will use
  the checker's recomputed times, not a method's totals.

### Test results
`pixi run test`: 27 passed (26 loader tests, including required tests 2 and 3, plus one
environment check). Manual runs: edge_case rejected with exit 1 and no decision.json;
hand_checkable and development_large load with exit 0.

### Current best scores
None yet. No method exists. Target to reproduce first: the rule to beat gives total
weighted tardiness 281 and total waiting 13 on hand_checkable (worked example).

### Next steps
1. Act on the reviewer's findings for the loader (review was running at handoff).
2. On a new `methods` branch: rule to beat plus required test 1 (reproduce
   worked-example/solution.json and metrics.json exactly).
3. Independent checker (never imports method code).
4. Iterated Greedy with NEH-style insertion, fixed seed, iteration-count stopping.
   Use numpy for schedule evaluation and time one development_large run early.
5. `pixi run tune` (grid: d in 2, 4, 6, 8; iterations 500, 1000, 2000; 5 seeds;
   small, medium, large), then the tuner subagent.
