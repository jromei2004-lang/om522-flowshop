# Prototype plan (OM 522 Option 6)

Team: John Romei, James Conte. Prepared 2026-10-20 against `docs/team-project-guide.pdf`
("Revised October 14, 2026"): Table 2 (Prototype row) and Section 4.1 (Prototype rubric).

Every command output below was run on 2026-10-20 on John's laptop (Windows 11, Intel Core
i5-1135G7) from `main` at commit `1b5f4f3` (tuned defaults merged). The comparison table comes
from `results/comparison.csv`, produced by `pixi run compare` on the same laptop with the same
code on 2026-10-19. Measures are the independent checker's recomputation, not a method's own
report.

What the October 14 revision changed for us: the prototype is now a check-in on our methods.
Tests 2 and 3, the comparison on three instances, and naming the uncertain input moved to the
final submission. We already have all of them, so we can mention them briefly, but nothing in
the prototype grade depends on them.

| Rubric criterion (Section 4.1) | Points | Status |
| --- | ---: | --- |
| 1. Ingestion and the rule to beat | 5 | Done, needs recording |
| 2. Independent checker | 4 | Done, needs recording |
| 3. Researched method and rationale | 5 | Method done; explanation drafted below, needs recording |
| 4. First implementation | 3 | Done (all four instances), needs recording |
| 5. Recording | 3 | Not recorded yet; outline below |

---

## 1. Ingestion and the rule to beat (5 points)

**What the guide requires.** The tool reads a fresh supplied instance without code edits,
applies the four input checks (files and columns present, declared types, identifiers exist,
processing times positive), and reports failures clearly. The rule to beat reproduces the worked
example's decision and measures (test 1 passes) and writes decision.json.

**What we have.**
- Loader: `src/flowshop/loader.py`. Command line: `src/flowshop/cli.py`
  (`pixi run solve <input_dir> <output_dir> [--method ig|rule]`).
- Rule to beat: `src/flowshop/rule_to_beat.py` (earliest due date, ties by job id), timing in
  `src/flowshop/schedule.py`. Decision file: `src/flowshop/decision.py`.
- Test 1: `tests/test_rule_to_beat.py::test_rule_reproduces_worked_example`.
- Input checks: `tests/test_loader.py`, including test 2
  (`test_edge_case_is_rejected`) and test 3 (`test_deleted_required_column_is_rejected`), plus
  `test_text_in_integer_column`, `test_unknown_job_id`, `test_negative_processing_time`,
  `test_missing_file`, `test_shuffled_rows_give_same_instance`, `test_input_files_unchanged`.
- Full suite: `pixi run test` gives **136 passed in 21.87 s**.

**Commands for the video** (PowerShell, from the repo folder):
```powershell
New-Item -ItemType Directory $env:TEMP\om522-demo
Copy-Item -Recurse data\development_small $env:TEMP\om522-demo\fresh_small
pixi run solve $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\rule_small --method rule
pixi run solve data\edge_case $env:TEMP\om522-demo\edge_out
pixi run test tests/test_rule_to_beat.py::test_rule_reproduces_worked_example -v
```

**Actual output.**
```
Method: Rule to beat (earliest due date, ties by job id)
Stopping rule: single construction pass (no search)
Status: feasible decision written to decision.json
Instance: C:\Users\jrome\AppData\Local\Temp\om522-demo\fresh_small (15 jobs, 8 stages)
Total weighted tardiness: 1417
Total waiting between stages: 732
Computation time (s): 0.0001 (includes numba load and compile for ig)
```
```
Input rejected: data\edge_case
  - processing_times.csv, column processing_time, line 2: job J001 at stage S1 has 0 (must be positive)
No decision.json was written.
```
(exit status 1, and no decision.json in `edge_out`)
```
tests/test_rule_to_beat.py::test_rule_reproduces_worked_example PASSED   [100%]
============================== 1 passed in 0.77s ==============================
```

**Still missing.**
- The summary line "(includes numba load and compile for ig)" also prints for `--method rule`,
  which is confusing on video. Fix in `cli.py` before recording. Owner: John.

---

## 2. Independent checker (4 points)

**What the guide requires.** Separate code recomputes feasibility and the measures from the
input files and an exported decision, and confirms the rule's decisions on the worked example
and one development instance.

**What we have.**
- Checker: `src/flowshop/checker.py` (`pixi run check <input_dir> <decision.json> [--report]`;
  exit 0 feasible, 1 infeasible, 2 cannot read input or decision). It imports nothing from the
  methods: `tests/test_checker.py::test_checker_imports_no_flowshop_code` and
  `test_running_checker_loads_no_other_flowshop_module`.
- Worked example: `test_worked_example_is_feasible_with_reference_measures`,
  `test_report_matches_worked_example`. Rule on development instances:
  `test_rule_decision_on_development_small_is_feasible`,
  `test_rule_decision_feasible_on_other_dev_instances`.
- It names the job and rule for each violation (`test_overlap_on_a_stage`,
  `test_start_before_release`, `test_swapped_sequence_is_infeasible`, and others), and enforces the
  1e-8 duration tolerance (`test_duration_within_1e8_is_accepted`,
  `test_duration_beyond_1e8_is_rejected`).

**Commands for the video** (after section 1's commands):
```powershell
pixi run check data\hand_checkable data\worked-example\solution.json
pixi run solve data\hand_checkable $env:TEMP\om522-demo\rule_hand --method rule
pixi run check data\hand_checkable $env:TEMP\om522-demo\rule_hand\decision.json
pixi run check $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\rule_small\decision.json
```

**Actual output.**
```
Checking data\worked-example\solution.json against data\hand_checkable
Status: FEASIBLE (every required constraint holds)
Recomputed measures:
  Total weighted tardiness: 281
  Total waiting between stages: 13
  Makespan: 139
```
Our rule's own decision on hand_checkable: FEASIBLE, 281, 13, makespan 139 (same as the worked
example's `metrics.json`: 281, 13, 139).
```
Checking ...\om522-demo\rule_small\decision.json against ...\om522-demo\fresh_small
Status: FEASIBLE (every required constraint holds)
Recomputed measures:
  Total weighted tardiness: 1417
  Total waiting between stages: 732
  Makespan: 417
```
All three exit with status 0.

**Still missing.** Nothing for the prototype.

---

## 3. Researched method and rationale (5 points)

**What the guide requires.** The video names the researched method and its published source,
explains how it represents and builds a solution and when it stops, and gives a specific reason
to expect it to beat the rule on this option.

**What we have.** `src/flowshop/iterated_greedy.py` (method) and `src/flowshop/fast_eval.py`
(fast scoring), notes in the README ("Tuning" and "Iterated Greedy notes"). Tests in
`tests/test_iterated_greedy.py` and `tests/test_fast_eval.py`.

### The method in plain words

**Source.** Iterated Greedy from Ruiz and Stützle (2007, *European Journal of Operational
Research*), which is one of the readings the option 6 brief names. Its construction step is the
NEH insertion heuristic from Nawaz, Enscore, and Ham (1983, *Omega*), also named in the brief.
Both papers were written for makespan; we adapted them to weighted tardiness.

**How a solution is represented.** One list of all jobs, for example
J001, J002, J003, J004, J006, J005. Every stage processes the jobs in that order. Given the list,
the timing is fixed: each job starts a stage as soon as both the job (released, or done at the
previous stage) and the stage (done with the previous job) are ready. So the method only has to
choose the order; the start times follow from it.

**How it builds a solution (NEH start).** Take the jobs in due date order. Place the first one.
Then take each next job and try it in every possible position of the partial list, keeping the
position with the lowest weighted tardiness. Then run local search (below) on the full list.

**How it improves a solution (repeated 1,000 times).**
1. Destruction: remove 6 jobs chosen at random.
2. Construction: put them back one at a time, each into its best position (same insertion step
   as NEH).
3. Local search: take each job in random order, pull it out, and reinsert it in its best
   position. Repeat full passes until a pass finds no improvement.
4. Acceptance: if the new list is better, keep it. If it is worse, sometimes keep it anyway, with
   a probability that shrinks as it gets worse, exp(-(new - current) / T). This lets the search
   leave a local dip instead of getting stuck. T = Tp x average weight x total processing time /
   (jobs x stages x 10), with Tp = 0.8. The average weight factor is our own adaptation, because
   the paper's formula is in minutes and ours is in weighted minutes.
5. The best list ever seen is the answer. The EDD list counts as seen, so the result is never
   worse than the rule.

**Stopping rule and seed.** Stops after exactly 1,000 iterations. Random choices use seed 522,
so a rerun gives the same decision (`test_same_seed_same_decision`,
`test_same_result_in_separate_processes`). A 480 second time limit exists only as a safety cap
and has never been reached (every run prints "iteration count reached (1000)"). The settings d = 6
and Tp = 0.8 were chosen by a tuning grid on the three development instances only (README,
"Tuning").

### Three reasons it should beat EDD on option 6, from our data

These are from the checker-verified decisions in `results/runs/` (the run behind
`results/comparison.csv`), recomputed with a read-only script.

1. **EDD ignores weights.** EDD sorts by due date only, so a weight 1 job can go ahead of a
   weight 4 job. On hand_checkable it puts J005 (weight 1, due 67) ahead of J003 (weight 4, due
   81), and J006 (weight 2) ahead of J004 (weight 4). The weight 4 jobs cost 200 of EDD's 281.
   The best order (233) moves J005 to the end, and the weight 4 jobs then cost 76. On
   development_large, a lower weight job sits directly ahead of a higher weight job in 50 of 119
   neighboring pairs of the EDD list; 16 weight 5 jobs are late and cost 5,230 of the 23,015.
   With Iterated Greedy, 5 weight 5 jobs are late and they cost 375.
2. **EDD ignores release times and how processing times stack up across 8 stages.** It never
   looks at when a job arrives or how long it takes at each stage, so a job that is slow at a
   later stage can block everything behind it. That shows up as waiting between stages: EDD
   waits 732, 2,040, and 7,863 on small, medium, and large; Iterated Greedy waits 323, 862, and
   3,713, even though waiting is not what it optimizes. It also shows in late jobs: EDD has 10,
   34, and 92 late jobs; Iterated Greedy has 2, 4, and 45. Iterated Greedy scores every move on the
   full 8 stage timing with releases, so it accounts for both effects.
3. **Iterated Greedy directly minimizes weighted tardiness.** Every insertion and every
   acceptance decision uses the exact total weighted tardiness of the full schedule. The NEH
   start alone already cuts EDD's 1,417 / 2,371 / 23,015 to 30 / 130 / 4,908, and the 1,000
   iterations bring that to 21 / 58 / 4,246. On hand_checkable it reaches 233, which is the best
   of all 720 possible orders (only one order reaches it).

**Commands for the video.** None needed for the explanation itself; show
`src/flowshop/iterated_greedy.py` lines 1 to 31 (the step list in the docstring) while talking.

**Still missing.**
- The README does not yet describe each method as guide Section 2.3 asks (representation,
  steps, stopping rule, seed, limitations). This section can be the starting draft, rewritten in
  our own words. Owners: John (Iterated Greedy), James (rule to beat).

---

## 4. First implementation (3 points)

**What the guide requires.** A first version runs on at least one development instance, its
decision passes the checker, and the video compares it with the rule on the primary and
secondary measures without claims the evidence does not support.

**What we have.** `pixi run compare` (`src/flowshop/compare.py`) runs both methods through
`pixi run solve` on all four instances, checks every decision with the checker, and writes
`results/comparison.csv` and `results/figures/comparison_bars.png`. All 8 decisions are feasible.

**Commands for the video** (after section 2's commands):
```powershell
pixi run solve $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\ig_small
pixi run check $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\ig_small\decision.json
Invoke-Item results\figures\comparison_bars.png
```

**Actual output.**
```
Method: Iterated Greedy (Ruiz and Stützle 2007) with NEH-style insertion, from EDD
Settings: iterations=1000, d=6, seed=522, Tp=0.8, safety time cap=480 s
Stopping rule: iteration count reached (1000); iterations run: 1000
Rule to beat (EDD) weighted tardiness: 1417
After NEH and local search: 30
Status: feasible decision written to decision.json
Total weighted tardiness: 21
Total waiting between stages: 323
Computation time (s): 1.3138 (includes numba load and compile for ig)
```
```
Status: FEASIBLE (every required constraint holds)
Recomputed measures:
  Total weighted tardiness: 21
  Total waiting between stages: 323
  Makespan: 357
```

**Comparison table** (from `results/comparison.csv`; every measure is the checker's).
Computer: John's laptop, Windows 11, Intel Core i5-1135G7 @ 2.40 GHz. Time limit: the rule has
none (one pass); Iterated Greedy stops at 1,000 iterations with a 480 s safety cap, never reached.

| Instance | Jobs x stages | EDD TWT | IG TWT | TWT change | EDD waiting | IG waiting | EDD time (s) | IG time (s) | Checker |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| hand_checkable | 6 x 4 | 281 | 233 | -17.1% | 13 | 37 | < 0.0001 | 0.62 | both feasible |
| development_small | 15 x 8 | 1,417 | 21 | -98.5% | 732 | 323 | 0.0001 | 1.23 | both feasible |
| development_medium | 45 x 8 | 2,371 | 58 | -97.6% | 2,040 | 862 | 0.0002 | 2.94 | both feasible |
| development_large | 120 x 8 | 23,015 | 4,246 | -81.6% | 7,863 | 3,713 | 0.0010 | 12.89 | both feasible |

IG times include loading numba's compiled code. Run times vary on the same laptop with the same
result (development_large took 12.9 s in this compare run and 14.7 s on 2026-10-20).

**Windows vs Mac.** With the earlier defaults (d = 4, Tp = 0.4), James's Mac (Apple M2) and
John's laptop gave identical weighted tardiness and waiting on all four instances
(233 / 21 / 58 / 4,276 and 37 / 261 / 1,010 / 3,722; progress.md and findings.md, 2026-10-19).
Only the run times differed. The tuned defaults (d = 6, Tp = 0.8) have so far been run only on
John's laptop, so the Mac match for the numbers in this table is not yet confirmed (see the
checklist).

**What the evidence does and does not show.** On these four synthetic instances, Iterated Greedy
cuts total weighted tardiness a lot: by 17% on the 6 job case and by 82% to 99% on the
development instances, with every decision confirmed feasible by our independent checker. On the
6 job case it lowers weighted tardiness from 281 to 233, which we verified is the best possible
by scoring all 720 orders, but it raises waiting between stages from 13 to 37, so a better
primary measure can cost something on the secondary one. On all three development instances it
improves both measures. It does not prove that 21, 58, or 4,246 are optimal; only the 6 job case
was checked exhaustively. It has not been run on the held-out case (we never use it) or under
uncertain processing times (the stress test is a final submission item). These results come
from one seed per instance; in the tuning runs over seeds 1 to 5, this setting's development_large
result ranges from 4,159 to 4,358 (mean 4,211, standard deviation 84).

**Rule run time shows as 0.0.** The summary prints run time to 4 decimals, so the rule's
hand_checkable time (well under 0.1 ms) prints as 0.0000 and lands in `comparison.csv` as 0.0.
That reads as "took no time", which is not true. Suggested fix (John, `cli.py` and
`compare.py`, not method code): record the time with more digits, for example
`{runtime:.6f}` or in milliseconds, and in written tables report it as "< 0.0001 s" (as above)
rather than 0.0.

**Still missing.**
- James reruns `pixi run compare` on the Mac with the tuned defaults and confirms the TWT and
  waiting columns match this table. Owner: James.
- Runtime display fix above. Owner: John.

---

## 5. Recording (3 points)

**What the guide requires.** At most 10 minutes. Shows fresh input and actual outputs, and every
member walks through one component a coding agent drafted: what it does, one thing that was
wrong or unclear in the agent's version, and how we checked it. Unlisted YouTube video viewable
without requesting access.

**Plan: 8 minutes 45 seconds**, leaving 75 seconds of margin under the limit.

| Time | Segment | Length | Who |
| --- | --- | ---: | --- |
| 0:00 to 0:45 | The decision in our own words | 45 s | John |
| 0:45 to 1:45 | Fresh instance demo | 1 min | John |
| 1:45 to 2:15 | Test 1 passing | 30 s | James |
| 2:15 to 3:15 | Checker confirms the rule | 1 min | James |
| 3:15 to 5:15 | Researched method explanation | 2 min | John |
| 5:15 to 6:45 | Iterated Greedy run, checker, comparison chart | 1.5 min | John |
| 6:45 to 7:45 | John's walk-through | 1 min | John |
| 7:45 to 8:45 | James's walk-through | 1 min | James |

**Before recording:** delete the old demo folder so the copy is truly fresh, and close other
programs so run times are typical.
```powershell
Remove-Item -Recurse -Force $env:TEMP\om522-demo -ErrorAction SilentlyContinue
```

**0:00 to 0:45, the decision.** No commands. A production planner chooses the order in which
jobs enter an 8 stage line; every stage uses that same order. The tool reads the job and stage
files and returns one sequence with start and finish times at every stage, aiming to keep late
work low, with important jobs counting more. (Write this in our own words; it should match the
README opening paragraph.)

**0:45 to 1:45, fresh instance demo.**
```powershell
New-Item -ItemType Directory $env:TEMP\om522-demo
Copy-Item -Recurse data\development_small $env:TEMP\om522-demo\fresh_small
Get-ChildItem $env:TEMP\om522-demo\fresh_small
pixi run solve $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\rule_small --method rule
pixi run solve data\edge_case $env:TEMP\om522-demo\edge_out
```
Say: same files, new folder, no code edits; rule gives 1,417 and writes decision.json. Then the
edge case is rejected, naming `processing_times.csv`, column `processing_time`, with no
decision.json.

**1:45 to 2:15, test 1.**
```powershell
pixi run test tests/test_rule_to_beat.py::test_rule_reproduces_worked_example -v
```
Say: the test compares our sequence, every start and completion, and both measures (281 and 13)
with the worked example.

**2:15 to 3:15, checker confirms the rule.**
```powershell
pixi run check data\hand_checkable data\worked-example\solution.json
pixi run solve data\hand_checkable $env:TEMP\om522-demo\rule_hand --method rule
pixi run check data\hand_checkable $env:TEMP\om522-demo\rule_hand\decision.json
pixi run check $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\rule_small\decision.json
```
Say: the checker reads only the input CSV files and decision.json and recomputes everything;
281 / 13 on the worked example and our rule's decision, 1,417 / 732 on development_small.

**3:15 to 5:15, researched method.** Show `src/flowshop/iterated_greedy.py` lines 1 to 31 and
walk through section 3 above: source, one job list, NEH start, destroy / rebuild / local search /
accept, 1,000 iterations with seed 522, and the three reasons with their numbers.

**5:15 to 6:45, Iterated Greedy run, checker, comparison.**
```powershell
pixi run solve $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\ig_small
pixi run check $env:TEMP\om522-demo\fresh_small $env:TEMP\om522-demo\ig_small\decision.json
Invoke-Item results\figures\comparison_bars.png
```
Say: 1,417 to 21 on the fresh copy, confirmed feasible by the checker. Then the chart for all four
instances, and the "does and does not show" points: big gains on synthetic data, waiting goes up
on the 6 job case, not proven optimal beyond 6 jobs, not yet tested on held-out data or under
uncertainty.

**6:45 to 7:45, John's walk-through: `src/flowshop/fast_eval.py`.**
- What it does: computes every start and completion with numba (a general compiler, not a
  scheduling solver) and, using saved partial schedules, scores every insertion position for a
  job without rebuilding the whole schedule each time. This is what makes 1,000 iterations on
  120 jobs take seconds.
- What the agent got wrong: its README text claimed the fast evaluator and `schedule.py` always
  give exactly the same weighted tardiness. That is only true for whole-number data; with
  decimals they add the jobs in a different order and can differ in the last digits. Caught by
  the reviewer subagent (agent_log.md, Iterated Greedy review).
- How we checked: tests that both give identical times and tardiness on all four instances,
  every decision.json is written from `schedule.py`, the method stops with a clear error (exit 2)
  if the two disagree, and the checker confirms the result independently.
```powershell
pixi run test tests/test_fast_eval.py -v
```
Actual output: 8 passed in 1.05 s (`test_times_and_tardiness_match_schedule_py` and
`test_prefix_shortcut_matches_full_recompute`, each on hand_checkable and the three development
instances).
Backup example if needed: when NEH plus local search did not beat EDD, the agent's first version
started the search from raw EDD, which the paper does not do (agent_log.md, same review).

**7:45 to 8:45, James's walk-through: `src/flowshop/checker.py`.**
- What it does: reads only the input CSV files and decision.json, checks every constraint
  (each job at every stage once, same sequence everywhere, release, stage order, one job at a
  time, durations within 1e-8), names the job and rule for each violation, and recomputes the
  measures. It imports no method code.
- What the agent got wrong: the overlap check only compared each operation with its neighbor
  after sorting by start time, so when one long operation covered several others, only the first
  overlap was reported. Caught by the reviewer subagent (agent_log.md, checker). Fixed by
  comparing each operation with the latest finishing one before it.
- How we checked: a test that builds exactly that case and asserts every overlapped job is
  named, plus a test that the checker imports nothing from the methods.
```powershell
pixi run test tests/test_checker.py -v -k "overlap or imports_no"
```
Actual output: 5 passed, 50 deselected in 0.70 s, including
`test_overlap_reports_every_job_inside_a_long_operation` and
`test_checker_imports_no_flowshop_code`.
Backup example: the first tolerance test moved a time by 5e-8, which also broke other rules, so
it would have passed with no duration check at all (agent_log.md, checker).

If James records his parts on the Mac, replace `$env:TEMP\om522-demo` with `/tmp/om522-demo`,
`Copy-Item -Recurse` with `cp -R`, and backslashes with forward slashes.

---

## Checklist before November 3

Owners are proposed; confirm between us.

- [ ] Review and merge this pull request (`john/prototype-plan`). Owner: James.
- [ ] Fix `cli.py` so the "numba load and compile" note prints only for Iterated Greedy, and
      record run time with more digits (`cli.py`, `compare.py`); rerun `pixi run compare` and
      `pixi run test`. Owner: John.
- [ ] Rerun `pixi run compare` on the Mac with the tuned defaults and confirm TWT and waiting
      match the table in section 4. Owner: James.
- [ ] README opening paragraph on the decision in our own words (guide 2.1). Owners: John and
      James together.
- [ ] README method write-up for both methods (guide 2.3). Owners: John (Iterated Greedy), James
      (rule to beat).
- [ ] README names the tools used (guide 2.9: Claude Code, Pixi, numba). Owner: John.
- [ ] Write each walk-through script (about 150 words for 1 minute) and practice it. Owners: each
      member for their own.
- [ ] Dry run of the whole video with a timer; cut if over 9 minutes. Owners: both.
- [ ] Record from a clean `main` after the merges above; note the commit hash shown. Owners: both.
- [ ] Upload to YouTube as unlisted; open the link in a private window to confirm it plays
      without signing in. Owner: John.
- [ ] Confirm the repository is public, or that freem028@ua.edu has access. Owner: John.
- [ ] Submit the repository link, commit hash, and video link on Blackboard. Owner: John.
- [ ] Not needed for the prototype, but open: `pixi run tune` should run the checker itself
      (agent_log.md, tuning). Owner: John, after November 3.
