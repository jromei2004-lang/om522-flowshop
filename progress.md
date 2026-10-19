# Progress log

Newest entry first. See "Session handoff" in CLAUDE.md for when to update this file.

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
