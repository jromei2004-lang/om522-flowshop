# Agent log

Mistakes or gaps in agent-written code that we caught, and how.

## 2026-10-19: reviewer pass on loader (branch loader)
Caught by the reviewer subagent (read-only review against the guide and CLAUDE.md).
- A row with the wrong number of values was rejected with a message naming the file
  but not the column, which the guide requires. Not fixed yet (loader-fixes branch).
- The "no decision.json" assertions in required tests 2 and 3 could not fail, because
  nothing wrote decision.json yet. Fixed on john/rule-to-beat with a test that a valid
  input does write decision.json.
- A header-only stages.csv or jobs.csv was accepted. Not fixed yet.

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
