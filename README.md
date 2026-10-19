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

## Iterated Greedy notes

Speed tool: Iterated Greedy uses numba (`src/flowshop/fast_eval.py`) only to make schedule evaluation fast. It is a general-purpose compiler, not a scheduling solver, and its logic matches the plain-Python reference `src/flowshop/schedule.py`. `tests/test_fast_eval.py` checks that both give exactly the same start times, completions, and weighted tardiness on hand_checkable and all three development instances, and every decision.json is written from `schedule.py`.

Assumption (temperature scaling): Ruiz and Stützle (2007) set the acceptance temperature to T = Tp × (sum of processing times) / (n × m × 10). That formula was built for makespan, so it is measured in minutes. Our objective is weighted tardiness, measured in weighted minutes, so we multiply it by the average job weight: T = Tp × (average weight) × (sum of processing times) / (n × m × 10). This scaling is our own adaptation, not from the paper, and Tp is included in the tuning grid.

Other Iterated Greedy adaptations and limitations:
- NEH order: the original NEH inserts jobs by decreasing total processing time, a makespan idea. We insert them in EDD order because due dates drive tardiness. The search then starts from the NEH sequence after local search, as in the paper, and the EDD sequence only competes for best so far, so the result is never worse than the rule to beat.
- Tp = 0 gives a temperature of 0, which accepts only strict improvements (equal sequences are not accepted). Tp = 0 is not used by default or in tuning.
- The time limit is a safety cap only, checked before each iteration. The initial NEH and local search are not covered by it. Iterations, not time, are the stopping rule.
- Cross-platform reproducibility: acceptance compares a random number to exp(...), and exp can differ in the last digit between Windows and Mac math libraries. A run could take a different path only if a comparison lands exactly on such a value, which is very unlikely. To confirm, run `pixi run solve` on a supplied instance on both machines and compare decision.json.
- On data with decimal values, the fast evaluator and schedule.py add tardiness in a different job order, so totals can differ in the last digits. Search comparisons use a relative tolerance of 1e-9, and the reported measures always come from schedule.py.
