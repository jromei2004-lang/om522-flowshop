# Agent log

Mistakes the coding agent made that we caught, newest first.

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
