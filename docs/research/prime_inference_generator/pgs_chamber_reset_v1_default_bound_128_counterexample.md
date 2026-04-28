# `pgs_chamber_reset_v1`: first default-bound obstruction at `128`

## Strongest supported finding

The default `candidate_bound = 128` Minimal PGS Generator v1.1 is not a true
next-prime theorem over all input primes `p >= 5`.

The first exact obstruction is:

$$
p = 1{,}357{,}201,\quad q = 1{,}357{,}333,\quad q-p = 132 > 128.
$$

At that anchor, `emit_record(1357201)` raises `PGSUnresolvedError`, while
`emit_record(1357201, candidate_bound=132)` returns `{"p": 1357201, "q": 1357333}`.

## Observable facts

- An exact prime-pair scan through `10^7` found no earlier gap greater than
  `128`.
- The first gap strictly above `128` is `132`, between `1357201` and `1357333`.
- The exact-state reduction already closes the wrong-first-survivor branch for
  `p >= 5` once the true next prime lies inside the chamber:
  [pgs_chamber_reset_v1_exact_state_reduction.md](pgs_chamber_reset_v1_exact_state_reduction.md).

So this obstruction is a bound obstruction, not a selection-rule misfire.

## Consequence

The theorem status now splits cleanly:

1. default generator theorem with `candidate_bound = 128`: false;
2. exact-state chamber-selection theorem for `p >= 5` when `q-p <= H`: still
   closed in the affirmative;
3. larger-bound theorems, including the observed `1024` high-scale surface:
   still open as bound questions.

## Artifact

- [first_default_bound_128_counterexample.json](../../../output/gwr_proof/first_default_bound_128_counterexample.json)
