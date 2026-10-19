# Findings

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
