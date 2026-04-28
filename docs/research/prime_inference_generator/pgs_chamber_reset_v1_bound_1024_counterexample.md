# `pgs_chamber_reset_v1`: first certified obstruction above bound `1024`

## Strongest supported finding

The `candidate_bound = 1024` chamber is not a true next-prime theorem for
`pgs_chamber_reset_v1` on input primes `p >= 5`.

The earliest certified conventional prime gap in the public first-occurrence
table with

$$
q - p > 1024
$$

is

$$
p = 1{,}693{,}182{,}318{,}746{,}371,\quad q = 1{,}693{,}182{,}318{,}747{,}503,
\quad q-p = 1132.
$$

At that anchor:

- `emit_record(p, candidate_bound=1024)` raises `PGSUnresolvedError`;
- `emit_record(p, candidate_bound=1132)` returns
  `{"p": 1693182318746371, "q": 1693182318747503}`.

So the live obstruction is again a bound obstruction, not a wrong-first-survivor
obstruction.

## Observable facts

The exact-state reduction already closed the endpoint-selection branch for
`p >= 5` once the true next prime lies inside the chamber:
[pgs_chamber_reset_v1_exact_state_reduction.md](pgs_chamber_reset_v1_exact_state_reduction.md).

The remaining live question was therefore whether the larger production chamber
could still fail by missing the true next prime. This note answers that question
in the negative for `1024`.

Two deterministic inputs support the obstruction:

1. The prime-gap first-occurrence table maintained at the Prime Gap List shows
   the earliest certified conventional gap strictly larger than `1024` at
   `p = 1693182318746371`, with gap `1132`:
   [allgaps.sql](https://raw.githubusercontent.com/primegap-list-project/prime-gap-list/master/allgaps.sql).
2. Local exact verification confirms that both boundary integers are prime, no
   interior integer is prime, and the current Minimal PGS Generator v1.1 fails
   exactly at `candidate_bound = 1024` while resolving at the true gap width.

## Consequence

The theorem status now splits into these exact parts:

1. universal theorem over all primes: false at `p = 2` and `p = 3`;
2. exact-state chamber-selection theorem for `p >= 5` once `q` is inside the
   chamber: proved;
3. default `candidate_bound = 128` theorem: false;
4. larger `candidate_bound = 1024` theorem: false, with explicit obstruction
   above.

The next live bound question is no longer whether `1024` is universal. That is
closed. The next smallest deterministic bound branch is any larger fixed chamber
theorem the project wants to claim.

## Artifact

- [first_bound_1024_counterexample.json](../../../output/gwr_proof/first_bound_1024_counterexample.json)
