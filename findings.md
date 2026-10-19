# Findings

## Iterated Greedy vs rule to beat, provisional defaults (2026-10-19)

`pixi run solve data/<instance> <out>` with the provisional defaults: 1000 iterations,
d = 4, Tp = 0.4, seed 522. Run on John's laptop (Windows 11, Intel i5-1135G7). Time
includes numba load and compile (or cached compile). Measures recomputed by schedule.py,
not yet confirmed by the independent checker.

| Instance | Rule TWT | IG TWT | Reduction | After NEH + local search | IG time (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| hand_checkable | 281 | 233 | 17.1% | 233 | 1.3 |
| development_small | 1417 | 21 | 98.5% | 30 | 2.2 |
| development_medium | 2371 | 58 | 97.6% | 130 | 4.8 |
| development_large | 23015 | 4276 | 81.4% | 4908 | 24.7 |

- Results were identical before and after the reviewer fixes (start search from NEH,
  relative tolerance, final EDD guard), because NEH plus local search beat EDD on every
  instance.
- Two runs in separate processes give byte-identical decision.json (test).
- Iterated Greedy is a heuristic; these are not proven optimal.
- Defaults are provisional until the tuning grid is analyzed.

## Rule-to-beat baseline (2026-10-19)

Method 1, earliest due date with ties by job id, run with
`pixi run solve data/<instance> <out> --method rule` on branch `john/rule-to-beat`.
The rule is deterministic, so a rerun gives the same values.

| Instance | Jobs x stages | Total weighted tardiness | Total waiting between stages |
| --- | --- | ---: | ---: |
| hand_checkable | 6 x 4 | 281 | 13 |
| development_small | 15 x 8 | 1417 | 732 |
| development_medium | 45 x 8 | 2371 | 2040 |
| development_large | 120 x 8 | 23015 | 7863 |

- hand_checkable matches worked-example/solution.json and metrics.json exactly (test 1).
- The development values are the method's own numbers and have not yet been confirmed
  by the independent checker. Rerun the checker on these decisions once it is merged.
- Runtime is under 0.002 s on every instance, so it is not a factor for this rule.
- Iterated Greedy must beat these by more than 0.001 in total weighted tardiness.
