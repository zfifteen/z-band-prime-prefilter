# `pgs_chamber_reset_v1`: exact-state reduction and bottom-of-line obstruction

## Strongest supported finding

As a theorem over **every** input prime `p`, `pgs_chamber_reset_v1` is false.
The current rule has finite obstructions at `p = 2` and `p = 3`.

With the current wheel-open filter, the next primes `3` and `5` are not legal
candidate endpoints:

- `p = 2`, `q = 3`, offset `1`, but `(2 + 1) mod 30 = 3` is not in
  `WHEEL_OPEN_RESIDUES_MOD30`.
- `p = 3`, `q = 5`, offset `2`, but `(3 + 2) mod 30 = 5` is not in
  `WHEEL_OPEN_RESIDUES_MOD30`.

So the universal statement

$$
\text{for every prime } p,\ \texttt{pgs\_chamber\_reset\_v1}(p)=q
$$

already fails before any high-scale obstruction family is needed.

## Observable facts from the current implementation

The generator uses three load-bearing facts:

1. `admissible_offsets(p, H)` keeps only offsets whose endpoints land in
   `WHEEL_OPEN_RESIDUES_MOD30`.
2. `divisor_counts_segment(lo, hi)` returns exact divisor counts on the whole
   chamber.
3. Inside `pgs_chamber_reset_state_certificate`, a wheel-open offset is marked
   `RESOLVED_SURVIVOR` exactly when its divisor count is not greater than `2`
   and no earlier prime has already appeared in the scan.

Those facts are implemented in:

- [`src/python/z_band_prime_predictor/simple_pgs_generator.py`](../../../src/python/z_band_prime_predictor/simple_pgs_generator.py)
- [`src/python/z_band_prime_composite_field/field.py`](../../../src/python/z_band_prime_composite_field/field.py)

## Reduced theorem that survives the counterexample

The live theorem is smaller, but it is not yet closed by the argument above.

Let `p >= 5` be prime, let `q` be the actual next prime after `p`, and let

$$
g = q - p.
$$

The current exact-state implementation clearly reaches offset `g` when the
chamber bound `H` satisfies `g <= H`, and at that offset it initially labels
`q` as `RESOLVED_SURVIVOR`.

That is not the end of the proof.

## Why the direct proof path fails

The unresolved branch is the lower-divisor threat pass.

After the first scan, the code computes `threat_offset` and then rewrites every
candidate state with

$$
\text{offset} > \texttt{threat\_offset}
$$

to `REJECTED`.

So the earlier proof attempt fails at one exact point: if

$$
\texttt{lower\_d\_threat\_offset} < g,
$$

then the later threat rewrite rejects the already-labeled endpoint `q` before
the function returns.

The statement

$$
g \le H \Longrightarrow \texttt{pgs\_chamber\_reset\_v1}(p, H) = q
$$

is therefore not proved by the simple "first prime in the chamber" argument.
It still needs one more obstruction exclusion:

$$
\texttt{lower\_d\_threat\_offset} \ge g \quad \text{or} \quad \texttt{lower\_d\_threat\_offset} = \varnothing.
$$

## Exact finite check of the live branch

The smallest direct obstruction scan is now explicit:

- input domain: prime `p >= 5`;
- chamber rule: `H = q - p`;
- obstruction family: `lower_d_threat_offset < gap_offset`.

Artifact:

- [`output/gwr_proof/pgs_chamber_reset_v1_pre_q_threat_scan_1e6.json`](../../../output/gwr_proof/pgs_chamber_reset_v1_pre_q_threat_scan_1e6.json)

Exact result on the full prime-input surface `5 <= p <= 10^6`:

- checked prime pairs: `78,495`;
- gap-sized chamber failures: `0`;
- pre-`q` lower-divisor threats: `0`.

So the direct proof path fails logically, but the simplest live obstruction
family did not appear on the exact low-scale production surface.

## What this does and does not reduce

What is reduced:

- the universal theorem over all primes is already false because of `p = 2, 3`;
- for `p >= 5`, the live unresolved branch is now one exact inequality,
  `lower_d_threat_offset < gap_offset`.

What is not reduced:

- a proof that the inequality above is impossible for every prime input;
- a proof that chamber coverage alone is equivalent to resolution.

## What is closed and what remains open

Closed under exact divisor-count state:

- the universal all-primes theorem is false, with explicit finite obstructions
  `p = 2` and `p = 3`;
- the simplest pre-`q` threat obstruction did not occur on the exact surface
  `5 <= p <= 10^6` when `H = q - p`;
- every bound-only obstruction with `H < q - p` remains a pure no-survivor
  state, not a wrong-first-survivor state, on the committed examples.

Still open:

- whether there exists any prime `p >= 5` with
  `lower_d_threat_offset < gap_offset` in the exact gap-sized chamber;
- a proof or counterexample for that branch;
- a bound theorem proving that the production chamber always contains the next
  prime on the intended regime.

## Status after this reduction

The central theorem question now splits into three parts:

1. universal theorem over all primes: false, with explicit finite
   counterexamples `p = 2` and `p = 3`;
2. exact gap-sized chamber branch for `p >= 5`: no counterexample found
   through `p <= 10^6`, but the live obstruction is still
   `lower_d_threat_offset < gap_offset`;
3. production-bound theorem: even if the gap-sized branch is true, one still
   needs `q(p) - p <= H(p)` on the intended regime.

The next smallest deterministic obstruction check is therefore the first prime
input above `10^6` with either:

$$
\texttt{lower\_d\_threat\_offset} < \texttt{gap\_offset}
$$

or a proof that this inequality cannot occur.
