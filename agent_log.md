# Agent log

Mistakes the coding agent made that we caught, newest first.

## 2026-10-19 (tuning, branch john/tuned-defaults, Claude Code)

- **Runtime estimate for the grid was about 3x too low.** Before building `pixi run tune`
  the agent estimated about 1 hour for the full grid, then 35 to 40 minutes for 180 runs.
  Timing one setting on development_large first (John's instruction) showed 56 to 126 s
  per run, about 2 hours in total. Caught by that timing step, before the full grid ran.
- **`tune` does not run the checker.** John's spec said every tuning decision must pass the
  checker, but `tune.py` writes `checker = pending` and has no checking step. The 540
  decisions were checked afterwards with a one-off script outside the repo, and the results
  were written into the `checker` column (540 pass). Still open: `pixi run tune` alone does
  not reproduce that column. It should check each decision itself.
- **Runtimes in tuning.csv come from two sessions.** The agent started the grid, it was
  stopped, and it resumed in a later session when the laptop ran 1.5 to 2.3x faster. Small
  and the first 25 medium runs are slower than the rest. Caught by the agent when it reran
  two finished runs to confirm the code had not changed. Ranking used large-instance
  runtimes only, which all come from one session.
- **The tuner subagent first misread the 1% tie rule** as 1 point of weighted gap. Read
  literally, that would have picked d=2, Tp=0.8, 500 iterations, which is clearly worse on
  large (mean 4549 vs 4198). The tuner flagged and rejected this itself. The main session
  reran the ranking with "within 1% of the best mean TWT on medium and large", which gave
  the same choice (d=6, Tp=0.8, 1000).

## 2026-10-19 (Windows UTF-8, branch john/windows-utf8, Claude Code)

- **Encoding warning on Windows.** The agent-written test
  `test_same_result_in_separate_processes` passed on Mac but showed 2 warnings on Windows
  (`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xfc`). The child process printed
  "Stützle" in the Windows code page, where "ü" is byte 0xfc, and the test read its output
  as UTF-8. Caught by running the full suite on John's laptop. The agent's own Windows
  runs missed it because its shell set PYTHONIOENCODING=utf-8, which John's terminal does
  not. Fixed: `PYTHONUTF8 = "1"` under `[activation.env]` in pixi.toml, so every Pixi
  command uses UTF-8 on every platform. The test's subprocess call already used
  encoding="utf-8". Verified with that variable removed: 136 passed, 0 warnings.

## 2026-10-19 (compare, branch james/compare, Claude Code)

Caught by the reviewer subagent on the checker's new --report option:
- **Two completion sources.** The report gave each completion as start + processing time,
  while the measures used the decision's completion, so the two could disagree by up to 1e-8.
  Worse, for a decision that failed the duration check the report "corrected" the flagged
  operation (J003/S2 shown as [73, 76] instead of the decision's [73, 75]). Fixed: the report
  uses the decision's own start and completion, the same values the measures use.
- **Measures for infeasible decisions looked like results.** Now `measures` is null when
  infeasible and the values sit under `diagnostic_measures`.
- **A crashed check could reuse an old report.** A checker crash exited 1 (same as
  "infeasible") and compare read whatever check_report.json was left from the previous run.
  Fixed: the checker deletes an old report first and exits 3 on its own errors; compare also
  deletes the report before checking.
- **Chart labels rounded measures** (`:g` switches to scientific notation past 6 digits;
  `.3f` could hide a 0.0005 difference). Labels now show up to 9 decimals.
- **No time limit in the comparison**, which the guide (2.6) requires. Added time_limit_s and
  stopping_rule columns from summary.txt.
- **Weak report tests:** a message compared with itself, operations compared as a dict (hides
  duplicates), stage order tested only on an instance whose rows were already in order, and no
  tests for incomplete, invalid-sequence, or unreadable cases. All replaced or added.

Caught by the agent: a test used `shutil` without importing it at the top of the file (the
earlier tests imported it inside functions). The test failed with NameError; fixed.

## 2026-10-19: reviewer pass on loader (branch loader)
Caught by the reviewer subagent (read-only review against the guide and CLAUDE.md).
- A row with the wrong number of values was rejected with a message naming the file
  but not the column, which the guide requires. Fixed by James on james/loader-fixes
  (PR #3).
- The "no decision.json" assertions in required tests 2 and 3 could not fail, because
  nothing wrote decision.json yet. Fixed on john/rule-to-beat with a test that a valid
  input does write decision.json.
- A header-only stages.csv or jobs.csv was accepted. Fixed by James on
  james/loader-fixes (PR #3).

## 2026-10-19: reviewer pass on Iterated Greedy (branch john/iterated-greedy)
Caught by the reviewer subagent on iterated_greedy.py and fast_eval.py. Fixed before the
first commit of the method:
- The README claimed numba and schedule.py give exactly the same weighted tardiness.
  True for the supplied integer data only; with decimal data the job order of the sum
  differs. Fixed: relative tolerance in search comparisons, a final never-worse-than-EDD
  check on the schedule.py value, and the README now states the limit.
- With fewer than 2 jobs the summary still said "iteration count reached (1000)". Fixed.
- The summary printed the requested d, not the d actually used when d exceeds the
  number of jobs. Fixed.
- If NEH plus local search did not beat EDD, the search started from raw EDD, which the
  paper does not do. Fixed: the search always starts from NEH plus local search; EDD
  only competes for best so far. No score changed on the four instances.
- An internal mismatch error would end in a traceback. Fixed: clear message, no
  decision.json, exit 2.
- Missing tests for 0 jobs, 1 job, d larger than the job count, and reruns in separate
  processes. Added.
- Undocumented adaptations (NEH in EDD order, Tp = 0 behavior, time cap not covering
  NEH, tiny cross-platform exp risk). Documented in the README.
- Still open: the README does not yet describe each method as guide Section 2.3
  requires (representation, steps, stopping rule, seed, limitations).


## 2026-10-19 (checker, branch james/checker, Claude Code)

- **Weak tolerance test.** The first test of the 1e-8 duration tolerance moved J001's S1
  completion by 5e-8. That also caused an overlap with J002 and a stage-order violation, and
  the test only asserted "infeasible", so it would have passed with no duration check at all.
  Caught by the reviewer subagent. Fixed: each boundary (duration, release, stage order,
  overlap) is now moved on its own, both inside and outside 1e-8, and the test asserts which
  rule fired.
- **Wrong comment in the first fix.** The replacement tolerance test claimed to cover stage
  precedence but did not exercise it. Caught by the agent on rereading. Rewritten as above.
- **Overlap check missed jobs.** It compared only neighbouring operations after sorting by
  start, so when one operation spanned several others only the first was reported. Caught
  by the reviewer. Fixed by comparing each operation with the latest-finishing one before it.
- **Crash on a malformed decision.** A schedule entry whose job_id was a list or object raised
  a TypeError (traceback, exit 1, the same status as "infeasible"). A jobs.csv or stages.csv
  with a header but no rows also crashed. Caught by the reviewer. Fixed: non-string ids are a
  structure violation; empty files and blank ids give "Cannot check" with exit 2.
- **Weak assertions.** The overlap and unknown-job tests passed if only one of the expected
  violations was reported. Caught by the reviewer. They now assert each job and rule.
- **Wrong claim earlier in the session.** The agent said required test 1 might not exist yet,
  without checking. It already existed (merged from john/rule-to-beat). Caught when the agent
  read the tests.
