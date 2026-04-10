# Gap Winner Rule

## Statement

Inside each prime gap $(p, q)$ with at least one composite interior, assign each
interior integer $n$ the raw-$Z$ quantity

$$
Z_{\mathrm{raw}}(n) = n^{\,1 - d(n)/2}.
$$

For winner comparisons, the implementation uses the equivalent log-score

$$
L(n) = \ln Z_{\mathrm{raw}}(n) = \left(1 - \frac{d(n)}{2}\right)\ln(n).
$$

The Gap Winner Rule (GWR) says the log-score argmax, equivalently the raw-$Z$
argmax, is exactly the interior integer selected by this arithmetic order:

1. choose the smallest interior divisor count $d(n)$,
2. among interiors with that minimum, choose the leftmost one.

Equivalently, the log-score winner and the lexicographic winner are the same
carrier. The repo now closes this statement conditionally for all prime gaps
under BHP's $\theta = 0.525$ and the explicit divisor-function majoration
constants recorded in
[`gwr_universal_bridge_closure.md`](./gwr_universal_bridge_closure.md).

## Legacy Name

This rule was first recorded in this repo under the legacy name
`Lexicographic Winner-Take-All Peak Rule`.

Going forward:

- use `Gap Winner Rule` or `GWR` in new prose,
- retain the legacy name where existing titles, figure labels, or filenames
  already depend on it.

## Current Proof Surface

The historical validation surface includes:

- the committed legacy validation summary in
  [`benchmarks/output/python/gap_ridge/lexicographic_peak_validation/lexicographic_peak_validation.json`](../../benchmarks/output/python/gap_ridge/lexicographic_peak_validation/lexicographic_peak_validation.json)
- the extended revalidation summary in
  [`output/lexicographic_rule_revalidation_summary.json`](../../output/lexicographic_rule_revalidation_summary.json)

On those current surfaces, the repo reports zero counterexamples.

The current proof closure uses the exact finite bridge-load base
[`asymptotic_bridge_load_scan_2e7.json`](../../output/gwr_proof/asymptotic_bridge_load_scan_2e7.json)
and the explicit certificate
[`proof_bridge_certificate_2e7.json`](../../output/gwr_proof/proof_bridge_certificate_2e7.json).
The finite base records `1,163,198` gaps, `3,349,874` earlier candidates, and
`0` bridge failures through $p < 20{,}000{,}001$.

## Immediate Consequences

`GWR` compresses several observed features into one selection law:

- $d(n)=4$ winner dominance,
- left-half winner dominance,
- frequent edge-distance $2$ winners.

Those observations are not separate rules in the current interpretation. They
are consequences of the same winner law when it holds.
