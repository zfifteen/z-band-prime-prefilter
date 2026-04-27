# Next-Prime Law 003: First Selected-Integer-Bearing Search Interval Diagnostic Record

Next-Prime Law 003 moves the first positive target away from the empty input-prime-11
search interval. The target is a search interval where PGS has actual interior structure: a
composite interior, a definable GWR-selected integer, a divisor-count selected integer, and a
closure condition that can be inspected without classical endpoint detection.

This note uses the small search interval from input prime `13` to proposed endpoint `17` as
the first probe. It does not emit yet. It establishes the selected-integer-bearing
diagnostic record and identifies the remaining uniqueness gap.

## Name

First Selected-Integer-Bearing Search Interval Diagnostic Record.

The law asks whether a nonempty search interval with a GWR-compatible selected integer can force
its right endpoint from PGS structure alone.

## Target Probe

The first probe is:

$$p = 13$$

with proposed endpoint:

$$q_{hat} = 17$$

The proposed interior is:

$$I = \{14, 15, 16\}$$

This search interval is small enough to audit by hand and large enough to contain
nontrivial selected-integer structure.

## Allowed Inputs

- externally supplied input prime `p = 13`;
- proposed endpoint supplied by the candidate law, not by a next-prime oracle;
- deterministic factor witnesses for proposed interior composites;
- divisor counts derived from those explicit witnesses;
- GWR leftmost-minimum integer logic;
- no-later-simpler comparison against explicitly identified later interior
  points;
- deterministic wheel arithmetic.

## Forbidden Inputs

Next-Prime Law 003 must not use:

- Miller-Rabin;
- `nextprime`;
- `isprime`;
- `prime`;
- `prevprime`;
- trial-division primality testing as a endpoint test;
- sieve-backed divisor counting;
- scanning until `d(n) = 2`;
- the old recursive predictor;
- a committed prime list;
- hardcoded prime outputs;
- the fact that `17` is classically prime.

The string `17` may appear only as the proposed endpoint in the law probe. It
must not be used as a known prime.

## Proposed Search Interval Diagnostic Record

For the proposed interior:

$$I = \{14, 15, 16\}$$

the concrete composite witnesses are:

- `14 = 2 * 7`, so `d(14) = 4`;
- `15 = 3 * 5`, so `d(15) = 4`;
- `16 = 2^4`, so `d(16) = 5`.

The minimum divisor class inside the proposed interval is:

$$d_{min} = 4$$

The leftmost integer in that divisor-count class is:

$$w = 14$$

The selection metadata is:

- `winner_carrier_w: 14`
- `winner_offset: 1`
- `winner_divisor_count: 4`
- `winner_family: "semiprime"`

This is the first meaningful selected-integer-bearing diagnostic record in the Milestone 1
sequence.

## GWR Compatibility

The GWR requirement for the proposed interval is satisfied at the diagnostic record
level:

- every interior point has an explicit composite witness;
- the interior divisor counts are known from those witnesses;
- the minimum divisor class is `4`;
- the leftmost minimum-divisor integer is `14`.

This proves that the proposed interval has coherent GWR structure. It does not
by itself prove that the search interval endpoint is forced at `17`.

## No-Later-Simpler Closure

Inside the proposed interval after the selected integer:

- `15` has divisor count `4`, not lower than the selected integer;
- `16` has divisor count `5`, not lower than the selected integer.

There is no later lower-divisor interior threat before the proposed endpoint.

The local no-later-simpler status is:

- `closure_status: "no_later_simpler_inside_proposed_chamber"`
- `threat_margin: null`

This is an interior closure statement. It does not yet rule out a lower-divisor
threat after `17` if the search interval were allowed to continue.

## Competing Endpoint Analysis

The proposed endpoint `17` is wheel-open from input prime `13` at offset `4`.

Earlier positive offsets are:

- offset `1`: `14`, closed by concrete composite witness;
- offset `2`: `15`, closed by concrete composite witness;
- offset `3`: `16`, closed by concrete composite witness.

Therefore no smaller candidate next prime remains inside the proposed interval.

This establishes:

- the proposed interior is closed;
- the proposed interval has a GWR-selected integer;
- no smaller offset in the proposed interval can be the endpoint.

It does not establish that the first position after the closed selected-integer-bearing
search interval is uniquely forced as the right endpoint.

## Endpoint Uniqueness Gap

The current diagnostic record still separates three statements:

- `14`, `15`, and `16` are composite interior points;
- `14` is the GWR-compatible leftmost minimum-divisor integer;
- `17` is the first candidate after the closed proposed interval.

The missing implication is:

$$\text{closed selected-integer-bearing search interval with no later simpler interior threat} \Rightarrow \text{forced next prime}$$

That implication is stronger than search-interval consistency. It is not proved here.

## Current Status

Next-Prime Law 003 does not yet emit.

For the input prime-13 probe:

- `closure_status: "carrier_chamber_closed"`
- `competing_boundary_status: "no_smaller_candidate_inside_chamber"`
- `uniqueness_status: "unresolved"`
- `inference_status: "failed_closed"`
- `failure_reason: "MISSING_CARRIER_BOUNDARY_UNIQUENESS"`

The law succeeds at finding the first structurally meaningful PGS search interval. It
fails to prove that the search interval structure forces the right endpoint.

## Emission Rule

Pure mode may emit under `boundary_law_003` only when:

1. the proposed interior has deterministic factor witnesss;
2. the proposed interior has a GWR-compatible selected integer;
3. later lower-divisor threats are excluded or bounded by PGS structure;
4. all smaller proposed endpoint positions are closed;
5. a selected-integer-bearing uniqueness theorem forces `q_hat`.

Until those five conditions hold, pure mode must emit a failure record.

## Failure Contract

If the selected integer cannot be established, emit:

- `rule_set_version: "boundary_law_003"`
- `inference_status: "failed_closed"`
- `failure_reason: "NO_GWR_CARRIER"`

If the proposed interior cannot be fully closed, emit:

- `rule_set_version: "boundary_law_003"`
- `inference_status: "failed_closed"`
- `failure_reason: "INCOMPLETE_CHAMBER_CERTIFICATE"`

If lower-divisor threats remain unresolved, emit:

- `rule_set_version: "boundary_law_003"`
- `inference_status: "failed_closed"`
- `failure_reason: "UNRESOLVED_THREAT_CLOSURE"`

If the uniqueness theorem is missing, emit:

- `rule_set_version: "boundary_law_003"`
- `inference_status: "failed_closed"`
- `failure_reason: "MISSING_CARRIER_BOUNDARY_UNIQUENESS"`

## Next Search Direction

Next-Prime Law 003 shows that moving to a selected-integer-bearing search interval fixes the
degeneracy of the input prime-11 case, but it does not by itself solve endpoint
uniqueness.

The next proof task is to determine whether GWR/DNI plus no-later-simpler
closure can force a endpoint, or whether the current diagnostic records only validate
proposed intervals after a proposed endpoint has already been chosen.

If the latter is true, the missing theorem is not input prime-specific. It is a
general bridge from search-interval consistency to next-prime inference.
