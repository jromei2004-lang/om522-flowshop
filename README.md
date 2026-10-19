# om522-flowshop

Team: John Romei, James Conte

OM 522 Option 6 flow shop decision tool

## Commands

- `pixi run solve <input_dir> <output_dir>` writes `decision.json` and `summary.txt`.
- `pixi run check <input_dir> <decision.json>` runs the independent checker. It reads only
  the input CSV files and the decision file, reports each violated constraint with its job
  and stage, and recomputes total weighted tardiness, total waiting between stages, and
  makespan. Exit status: 0 feasible, 1 infeasible, 2 the input or decision file cannot be read.
- `pixi run test` runs all tests.
