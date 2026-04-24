# Boundary Law 005A Stress Tests

## Status

Boundary Law 005A passed two controlled one-axis stress tests.

This is offline theorem discovery. Boundary Law 005A remains candidate-grade only. Pure generator emission remains forbidden. Classical labels are external audit only.

## Configuration

Both stresses used the same base eliminator regime:

- single-hole positive witness closure: enabled
- carrier-locked pressure ceiling: enabled
- carrier-lock predicate: unresolved_alternatives_before_threat
- 005A higher-divisor locked absorption: enabled only in offline stress
- 005B: disabled

## Candidate-Bound Stress

The first stress changed one variable:

- candidate bound: 64 -> 128

The witness basis did not change:

- witness bound: 97

The anchor surface did not change:

- anchors: 11..1000000

## Candidate-Bound Stress Metrics

| field | value |
|---|---:|
| candidate_bound | 128 |
| witness_bound | 97 |
| anchor_range | 11..1000000 |
| row_count | 78494 |
| true_boundary_rejected_count | 0 |
| absorption_wrong_count | 0 |
| false_resolved_survivor_absorbed_count | 0 |
| unique_resolved_survivor_count | 36 |
| 005A_applied_count | 48 |
| 005A_correct_count | 48 |
| 005A_wrong_count | 0 |
| action_population_match | true |
| action_population_missed_count | 0 |
| first_failure_example | null |

## Witness-Bound Stress

The second stress changed one variable:

- witness bound: 97 -> 127

The candidate horizon returned to the prior audited value:

- candidate bound: 64

The anchor surface did not change:

- anchors: 11..1000000

## Witness-Bound Stress Metrics

| field | value |
|---|---:|
| candidate_bound | 64 |
| witness_bound | 127 |
| anchor_range | 11..1000000 |
| row_count | 78494 |
| true_boundary_rejected_count | 0 |
| absorption_wrong_count | 0 |
| false_resolved_survivor_absorbed_count | 0 |
| unique_resolved_survivor_count | 25 |
| 005A_applied_count | 31 |
| 005A_correct_count | 31 |
| 005A_wrong_count | 0 |
| action_population_match | true |
| action_population_missed_count | 0 |
| first_failure_example | null |

## Hard Gate

The hard pass condition was:

```text
true_boundary_rejected_count = 0
absorption_wrong_count = 0
false_resolved_survivor_absorbed_count = 0
action_population_match = true
```

Both stresses passed all four requirements.

## Result

005A remains candidate-grade and is stronger than before:

```text
005A: candidate-grade, action-population audited, candidate-bound stress passed, witness-bound stress passed, safe so far, narrow
```

Coverage under the larger candidate horizon improved:

- bound 64 integration: 31 applications, 25 unique resolved survivors
- bound 128 stress: 48 applications, 36 unique resolved survivors

Coverage under the larger witness basis did not broaden:

- witness bound 97 integration: 31 applications, 25 unique resolved survivors
- witness bound 127 stress: 31 applications, 25 unique resolved survivors

The rule remains narrow. It is not a complete generator.

## Why Pure Emission Remains Forbidden

These stresses do not approve pure generator emission because:

- 005A is still a candidate law, not a theorem
- the tests are offline
- labels are still used after action for audit
- coverage is still narrow
- shifted-window activation remains sparse from prior evidence
- no pure emission contract has been approved

The pure generator must remain fail-closed.

## Falsification Conditions

Quarantine or restrict 005A if any future run shows:

```text
true_boundary_rejected_count > 0
absorption_wrong_count > 0
false_resolved_survivor_absorbed_count > 0
action_population_match = false
```

One wrong absorption kills generator eligibility for the rule.

## Next Gate

The next safe gate is a shifted-window stress at the stronger candidate horizon:

```text
candidate_bound: 128
witness_bound: 97
anchors: 100000..200000 and 1000000..1100000
```

That preserves the witness basis and tests whether the larger candidate horizon remains safe off the origin surface.
