# Findings

## Tuning result and tuned defaults (2026-10-19)

2026-10-19 | IG grid d{2,4,6,8} x tp{0.2,0.4,0.8} x iters{500,1000,2000}, 5 seeds, dev small/medium/large only | best (tie rule, within seed noise of top score): d=6 tp=0.8 iters=1000 | weighted avg gap 91.41% (unweighted 92.59%), worst-case seed gap 81.07% (large) | est size-60 runtime ~6 s (upper bound 15.5 s) | raw top score d=6 tp=0.4 iters=2000 at 91.43%, difference inconclusive

- All 540 tuning decisions were rebuilt from their stored sequences and passed the
  independent checker with matching TWT (`checker` column in results/tuning.csv).
- Small: every setting and seed reaches 21. Medium: every setting with d >= 4 reaches 58
  on all seeds by 500 iterations. Only large separates settings.
- Tie rule: ranks 1 to 4 are the only settings within 1% of the best mean TWT on both
  medium and large (large means 4198 to 4211; seed-to-seed SD about 80). The fastest of
  them is d=6, Tp=0.8, 1000 iterations. The tuner first read "1%" as 1 point of weighted
  gap, which would have picked d=2, Tp=0.8, 500 (large mean 4549, medium worst 92); that
  reading was rejected.
- Convergence: from 1000 to 2000 iterations the large mean improves by 6 to 59 for the top
  three (d, Tp) pairs, below seed noise. 5000 iterations was not tested.
- Ranking runtimes use development_large only; all large runs were in one session. Small
  and the first 25 medium runs were made in an earlier session when the laptop was about
  1.5 to 2.3x slower.

### New defaults, checker-verified (seed 522, John's laptop, i5-1135G7)

| Instance | Rule TWT | IG TWT (old defaults d=4, Tp=0.4) | IG TWT (new defaults d=6, Tp=0.8) | IG waiting (new) | IG time (new) |
| --- | ---: | ---: | ---: | ---: | ---: |
| hand_checkable | 281 | 233 | 233 | 37 | 0.8 s |
| development_small | 1417 | 21 | 21 | 323 | 1.2 s |
| development_medium | 2371 | 58 | 58 | 862 | 2.8 s |
| development_large | 23015 | 4276 | 4246 | 3713 | 12.5 s |

All four decisions are feasible (checker exit 0). Waiting rose on small (261 to 323) and
fell on medium (1010 to 862) and large (3722 to 3713); waiting is the secondary measure and
was not part of the ranking.

## Checker-verified comparison, IG provisional defaults (2026-10-19)

After merging main (James's independent checker) into john/iterated-greedy. Each method
was run with `pixi run solve data/<instance> <out> --method ig|rule`, then
`pixi run check data/<instance> <out>/decision.json`. Every value below is the checker's
recomputation from the input files and decision.json, not the method's own number.
IG settings: 1000 iterations, d = 4, Tp = 0.4, seed 522. John's laptop (Windows 11,
Intel i5-1135G7); IG time includes numba loading its cached compiled code.

| Instance | Rule TWT | IG TWT | TWT reduction | Rule waiting | IG waiting | Rule makespan | IG makespan | IG time (s) | Checker |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| hand_checkable | 281 | 233 | 17.1% | 13 | 37 | 139 | 136 | 0.55 | both feasible |
| development_small | 1417 | 21 | 98.5% | 732 | 261 | 417 | 357 | 0.98 | both feasible |
| development_medium | 2371 | 58 | 97.6% | 2040 | 1010 | 781 | 756 | 2.19 | both feasible |
| development_large | 23015 | 4276 | 81.4% | 7863 | 3722 | 1812 | 1804 | 10.81 | both feasible |

- All 8 decisions are feasible (checker exit 0), and the checker's TWT equals each
  method's own TWT, so the method-side numbers in the earlier tables are confirmed.
- Secondary measure: IG also cuts total waiting on the three development instances, but
  raises it on hand_checkable (13 to 37). Lower tardiness does not always mean less
  waiting.
- Run time varies between sessions on the same laptop: development_large took 24.7 s
  earlier today and 10.8 s now with identical results. The cause is not known (likely
  power or background load). Both are far under the 10-minute limit, but runtimes in
  results/tuning.csv should be compared within one session.
- Iterated Greedy is a heuristic; these values are not proven optimal.

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
