# Next-Prime Law 002: Minimal Closed Search Interval Diagnostic Record

Next-Prime Law 002 is the next candidate after Next-Prime Law 001 failed to close.
The change is the standard of evidence. The law does not infer a endpoint from
first wheel-open admissibility alone. It requires a complete PGS search interval
diagnostic record that forces the proposed endpoint.

This is a design note, not an output-producing implementation. If the diagnostic record cannot
force a unique endpoint without classical primality lookup, pure mode must remain
failed closed.

## Name

Minimal Closed Search Interval Diagnostic Record.

The law asks whether a proposed endpoint can be outputted only after the generator
has a closed search-interval diagnostic record for the interval before it and a deterministic
reason that no smaller admissible endpoint competes with it.

## Candidate Contract

Given an input prime `p` and proposed endpoint `q_hat`, Next-Prime Law 002 may
output `q_hat` only if it can construct a diagnostic record with:

- input prime `p`;
- proposed endpoint `q_hat`;
- interior `I = {p + 1, ..., q_hat - 1}`;
- verified search-interval closure for every integer in `I`;
- GWR-compatible selected integer data, or an explicit empty-interval base case;
- no-later-simpler closure for the active selected-integer regime;
- no unresolved competing search interval with smaller admissible endpoint;
- an explicit reason `q_hat` is forced rather than merely allowed.

If any field is missing or unresolved, the law fails closed.

## Allowed Inputs

- the externally supplied input prime;
- a proposed endpoint supplied by a PGS rule, not by a primality oracle;
- deterministic wheel arithmetic;
- deterministic composite witnesses for interior values;
- PGS selected-integer metadata inside the proposed interval;
- GWR/DNI ordering of interior integers;
- no-later-simpler threat metadata when the search interval has a selected integer;
- a named empty-interval base case, if such a base case is proved.

## Forbidden Inputs

Next-Prime Law 002 must not use:

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
- hardcoded prime outputs.

Interior compositeness evidence is allowed only when it is a concrete
deterministic witness for an interior integer. It must not become a search for
the next prime endpoint.

## Diagnostic Record Shape

A Next-Prime Law 002 diagnostic record should record:

- `anchor_prime_p`;
- `proposed_boundary_q_hat`;
- `interior_start`;
- `interior_stop`;
- `interior_composite_witnesses`;
- `winner_carrier_w`;
- `winner_offset`;
- `winner_divisor_count`;
- `winner_family`;
- `first_open_offset`;
- `closure_status`;
- `threat_margin`;
- `competing_boundary_status`;
- `uniqueness_status`;
- `failure_reason`, if unresolved.

For an empty interval, the diagnostic record must state that no positive-offset integer
exists before the proposed endpoint and must identify the theorem that turns
that empty interval into a forced endpoint.

## Input prime-11 Probe

For the first input prime:

$$p = 11$$

The tempting proposed endpoint is:

$$q_{hat} = 13$$

The interior is:

$$I = \{12\}$$

The integer `12` has concrete composite witnesses from the wheel basis:

- `12 = 2 * 6`
- `12 = 3 * 4`

This establishes that the search interval interior before `13` is closed. It does not
establish that `13` is forced as the endpoint.

## GWR/DNI Relevance

For `p = 11` and `q_hat = 13`, the proposed interior contains no open composite
integer. The GWR-selected integer score functions are null. Therefore the standard GWR-selected integer and
no-later-simpler closure machinery has no positive integer to operate on.

Next-Prime Law 002 has two possible paths:

- prove an empty-interval base case that forces the first open endpoint;
- reject this input prime as outside the selected-integer-bearing GWR/DNI regime.

The first path would revive Next-Prime Law 001 with a stronger diagnostic record. The
second path keeps Milestone 1 blocked at input prime `11` and pushes the first
positive target to a later input prime with a nonempty search interval.

## Competing Endpoint Requirement

The law must separate three statements:

- the interior before `q_hat` is closed;
- `q_hat` is an admissible candidate next prime;
- `q_hat` is the unique inferred next prime.

Only the third statement permits output.

For input prime `11`, the current diagnostic record establishes the first two statements:

- `12` is composite by concrete witness;
- `13` is the first wheel-open admissible candidate.

It does not prove the third statement. The diagnostic record does not rule out the
possibility that the first open candidate is not forced by PGS structure.

## Current Status

Next-Prime Law 002 does not yet output.

For the input prime-11 probe:

- `closure_status: "interior_closed"`
- `competing_boundary_status: "no_smaller_open_candidate"`
- `uniqueness_status: "unresolved"`
- `inference_status: "failed_closed"`
- `failure_reason: "MISSING_UNIQUENESS_IMPLICATION"`

The law improves the evidence standard over Next-Prime Law 001, but the same
mathematical bridge remains missing for the empty-interval case.

## Exact Missing Theorem

The missing theorem is:

$$\text{closed minimal search interval plus first open candidate} \Rightarrow \text{forced next prime}$$

For input prime `11`, this reduces to:

$$12 \text{ closed and } 13 \text{ first open} \Rightarrow 13 \text{ forced as endpoint}$$

That implication is stronger than admissibility. It is not proved here.

## Output Rule

Pure mode may output under `boundary_law_002` only when:

1. every interior integer has a deterministic factor witness;
2. the proposed endpoint comes from a PGS rule rather than a primality oracle;
3. all smaller candidate next primes are ruled out by the search-interval diagnostic record;
4. a PGS uniqueness theorem forces `q_hat` as the next prime.

Until those four conditions hold, pure mode must output a failure record.

## Failure Contract

If the uniqueness theorem is missing, output:

- `rule_set_version: "boundary_law_002"`
- `inference_status: "failed_closed"`
- `failure_reason: "MISSING_UNIQUENESS_IMPLICATION"`

If the interior closure record itself is incomplete, output:

- `rule_set_version: "boundary_law_002"`
- `inference_status: "failed_closed"`
- `failure_reason: "INCOMPLETE_CHAMBER_CERTIFICATE"`

If a competing smaller admissible search interval remains unresolved, output:

- `rule_set_version: "boundary_law_002"`
- `inference_status: "failed_closed"`
- `failure_reason: "UNRESOLVED_COMPETING_BOUNDARY"`

## Next Search Direction

Next-Prime Law 002 identifies the same blocker more sharply: the project needs a
non-classical uniqueness theorem, not more admissibility evidence.

The next search should compare two regimes:

- empty-interval input primes, where a first-open closure theorem would be needed;
- selected-integer-bearing input primes, where GWR/DNI and no-later-simpler closure may have
  enough structure to force a endpoint.

The first positive output should come from whichever regime first supplies a
complete uniqueness bridge without classical endpoint detection.
