# Agent log

Mistakes the coding agent made that we caught, newest first.

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
