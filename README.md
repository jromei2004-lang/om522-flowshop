# om522-flowshop

Team: John Romei, James Conte

OM 522 Option 6 flow shop decision tool

## Commands

- `pixi run solve <input_dir> <output_dir>` writes `decision.json` and `summary.txt`. It runs
  Iterated Greedy with fixed default settings; `--method rule` runs the rule to beat instead.
- `pixi run check <input_dir> <decision.json>` runs the independent checker. It reads only
  the input CSV files and the decision file, reports each violated constraint with its job
  and stage, and recomputes total weighted tardiness, total waiting between stages, and
  makespan. Exit status: 0 feasible, 1 infeasible, 2 the input or decision file cannot be read.
- `pixi run compare` runs every method through `pixi run solve --method <m>` on
  hand_checkable and the three development instances, checks each decision with
  `pixi run check --report`, and writes `results/comparison.csv` (feasibility, total weighted
  tardiness, total waiting, makespan, runtime, CPU) plus Gantt charts and a comparison bar chart
  in `results/figures/`. All measures and chart times come from the checker's report, not from
  a method's own output. A method that `solve` does not offer yet is skipped with a message.
- `pixi run test` runs all tests.
- `pixi run tune` runs the Iterated Greedy tuning grid on the development instances and
  writes `results/tuning.csv`. It is resumable: finished runs are skipped.

## Tuning

Default settings: d = 6 jobs removed per iteration, Tp = 0.8, 1000 iterations, seed 522.

**Grid.** `pixi run tune` ran every combination of d (2, 4, 6, 8), Tp (0.2, 0.4, 0.8), and
iterations (500, 1000, 2000), with 5 seeds (1 to 5) each, on development_small, medium, and
large only. That is 36 settings and 540 decisions in `results/tuning.csv`. Each 2000-iteration
run also recorded its best sequence at 500 and 1000 iterations, which equals a separate shorter
run with the same seed (tested). Every one of the 540 decisions was rebuilt from its stored
sequence and passed the independent checker with the same weighted tardiness (`checker`
column).

**How we ranked.** Score = weighted average of each instance's mean gap versus the rule to beat
over the 5 seeds, with weights small 0.2, medium 0.4, large 0.4, because the held-out case has 60
jobs and small is solved equally by every setting (TWT 21). We kept only settings whose slowest
large-instance run was under 2 minutes (all 36 passed; the slowest was 38 s). We also looked at
the worst seed and the spread between seeds, so a setting that got lucky once does not win.

| Rank | d | Tp | Iterations | Weighted gap | Medium TWT mean (worst) | Large TWT mean (worst) | Slowest large run |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | 6 | 0.4 | 2000 | 91.43% | 58 (58) | 4198 (4334) | 30.6 s |
| 2 | 6 | 0.8 | 2000 | 91.42% | 58 (58) | 4205 (4358) | 30.2 s |
| 3 | 6 | 0.2 | 2000 | 91.41% | 58 (58) | 4207 (4334) | 33.7 s |
| **4** | **6** | **0.8** | **1000** | **91.41%** | **58 (58)** | **4211 (4358)** | **15.5 s** |
| 5 | 4 | 0.8 | 2000 | 91.35% | 58 (58) | 4242 (4329) | 27.3 s |

Rule to beat for reference: small 1417, medium 2371, large 23015. Runtimes are from John's
laptop (Intel i5-1135G7).

**Why rank 4 and not rank 1.** Ranks 1 to 4 are the only settings within 1% of the best mean
weighted tardiness on both medium and large. Their large means differ by at most 13 weighted
minutes, while results for one setting vary by about 80 between seeds, so the differences are
noise. Among tied settings we prefer the faster and simpler one: rank 4 needs half the
iterations and half the time. Going from 1000 to 2000 iterations lowered the large mean by only
6 for this setting, and medium does not change after 500 iterations. Estimated time on a
60-job instance is about 6 s (at most about 15 s), far under the 10-minute limit. The risk: its
worst large seed (4358) is the highest of the tied group, and the held-out case is a single run
with one seed.

**Seed.** The default seed 522 was fixed before tuning and is not one of the tuning seeds (1 to
5). We did not choose the seed by looking at results, which would overfit to the development
instances. With the default settings, `pixi run solve` gives weighted tardiness 233, 21, 58, and
4246 on hand_checkable, small, medium, and large, all confirmed by the checker.

## Iterated Greedy notes

Speed tool: Iterated Greedy uses numba (`src/flowshop/fast_eval.py`) only to make schedule evaluation fast. It is a general-purpose compiler, not a scheduling solver, and its logic matches the plain-Python reference `src/flowshop/schedule.py`. `tests/test_fast_eval.py` checks that both give exactly the same start times, completions, and weighted tardiness on hand_checkable and all three development instances, and every decision.json is written from `schedule.py`.

Assumption (temperature scaling): Ruiz and Stützle (2007) set the acceptance temperature to T = Tp × (sum of processing times) / (n × m × 10). That formula was built for makespan, so it is measured in minutes. Our objective is weighted tardiness, measured in weighted minutes, so we multiply it by the average job weight: T = Tp × (average weight) × (sum of processing times) / (n × m × 10). This scaling is our own adaptation, not from the paper, and Tp is included in the tuning grid.

Other Iterated Greedy adaptations and limitations:
- NEH order: the original NEH inserts jobs by decreasing total processing time, a makespan idea. We insert them in EDD order because due dates drive tardiness. The search then starts from the NEH sequence after local search, as in the paper, and the EDD sequence only competes for best so far, so the result is never worse than the rule to beat.
- Tp = 0 gives a temperature of 0, which accepts only strict improvements (equal sequences are not accepted). Tp = 0 is not used by default or in tuning.
- The time limit is a safety cap only, checked before each iteration. The initial NEH and local search are not covered by it. Iterations, not time, are the stopping rule.
- Cross-platform reproducibility: acceptance compares a random number to exp(...), and exp can differ in the last digit between Windows and Mac math libraries. A run could take a different path only if a comparison lands exactly on such a value, which is very unlikely. To confirm, run `pixi run solve` on a supplied instance on both machines and compare decision.json.
- On data with decimal values, the fast evaluator and schedule.py add tardiness in a different job order, so totals can differ in the last digits. Search comparisons use a relative tolerance of 1e-9, and the reported measures always come from schedule.py.
