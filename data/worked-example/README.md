# Worked example for option 6

Sequencing jobs through a common production line.

This example applies the option's rule to beat (defined in option-6-brief.pdf) to ../hand_checkable/. It shows one feasible decision and how every measure except computation time is recomputed from that decision. It is not an optimal answer. The rule to beat is the team's first method, and the team's researched method must outperform this rule by more than 0.001 on the instructor's held-out case. solution.json has the structure that a team's decision.json must use. metrics.json is a reference for testing, not a required output, and its key names are not graded (e.g., makespan is the final or project completion time, and on_time_rate is the on-time fraction). Counts such as jobs_completed are consistency checks, not additional measures. The JSON files keep full numeric precision, and the tables below round to three decimals. All times are in minutes.

The rule sequences jobs by earliest due date (ties by job identifier) and uses that sequence at every stage. Each operation starts at the later of the job finishing its previous stage (or its release, at stage S1) and the stage finishing the previous job. Waiting between stages is the start at a stage minus the completion at the preceding stage.

## Decisions

Common sequence: J001, J002, J005, J003, J006, J004.

| Job id | Stage id | Start | Completion |
| --- | --- | --- | --- |
| J001 | S1 | 13 | 24 |
| J001 | S2 | 24 | 34 |
| J001 | S3 | 34 | 40 |
| J001 | S4 | 40 | 52 |
| J002 | S1 | 24 | 38 |
| J002 | S2 | 38 | 47 |
| J002 | S3 | 47 | 60 |
| J002 | S4 | 60 | 73 |
| J005 | S1 | 45 | 62 |
| J005 | S2 | 62 | 65 |
| J005 | S3 | 65 | 70 |
| J005 | S4 | 73 | 82 |
| J003 | S1 | 62 | 72 |
| J003 | S2 | 72 | 75 |
| J003 | S3 | 75 | 94 |
| J003 | S4 | 94 | 108 |
| J006 | S1 | 78 | 83 |
| J006 | S2 | 83 | 98 |
| J006 | S3 | 98 | 101 |
| J006 | S4 | 108 | 116 |
| J004 | S1 | 83 | 95 |
| J004 | S2 | 98 | 111 |
| J004 | S3 | 111 | 128 |
| J004 | S4 | 128 | 139 |

## Recomputed measures

| Measure | Value |
| --- | ---: |
| Final completion time | 139 |
| Total weighted tardiness | 281 |
| On-time fraction | 0.000 |
| Jobs completed | 6 |
| Total waiting between stages | 13 |
| Idle time by stage | S1 70; S2 86; S3 76; S4 72 |

The on-time fraction is between 0 and 1, not a percentage.
