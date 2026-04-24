# GPE Milestone 2 Implementation Status

The current implementation exposes the dominant $d(w)=4$ NLSC ceiling as a
branch validation surface, not as a completed selector theorem.

For one exact oracle row, the implemented surface records:

- current prime $q$,
- GWR winner $w$,
- winner divisor class $d(w)$,
- exact right boundary $q^+$ from the existing oracle,
- the branch horizon $S_{+}(w)$ when $d(w)=4$,
- the NLSC margin $S_{+}(w)-q^+$,
- and square-phase utilization $(q^+-w)/(S_{+}(w)-w)$ as a measured ratio.

The implementation lives in
[`../../src/python/z_band_prime_predictor/gpe_nlsc_selector.py`](../../src/python/z_band_prime_predictor/gpe_nlsc_selector.py).

## Current Deterministic Path

For $d(w)=4$, the row builder computes the validation horizon
$S_{+}(w)$ using the existing arithmetic definition of the next prime-square
threat. The branch selector then checks one straight-line contract:

$$q^+=q+\Delta,$$

where $\Delta$ is an explicit selector-state boundary offset. The selector also
verifies:

$$w<q^+\le S_{+}(w).$$

If $\Delta$ is absent, the selector fails explicitly. The NLSC ceiling alone is
not treated as an exact emission rule.

The implementation also exposes an executable branch-target audit:

[`../../src/python/z_band_prime_predictor/gpe_nlsc_selector.py`](../../src/python/z_band_prime_predictor/gpe_nlsc_selector.py)
defines `audit_nlsc_branch_targets(...)`, which groups an oracle validation
surface by observed $d(w)$ and reports whether each branch has an exact selector
law or an explicit unresolved target. On the focused branch smoke surface
`q in {3, 5, 11, 29}`, the observed classes are:

| $d(w)$ | Current status |
|---:|---|
| $3$ | unresolved target: define exact $B_3(q,S,w)$ |
| $4$ | ceiling and guarded selector surface exist; unresolved target: derive $q^+$ inside $(w,S_{+}(w)]$ without `boundary_offset` state |
| $6$ | unresolved target: define exact $B_6(q,S,w)$ |
| $8$ | unresolved target: define exact $B_8(q,S,w)$ |

## Validated Rows

The focused tests validate the first dominant branch examples:

| $q$ | $w$ | $d(w)$ | $q^+$ | $S_{+}(w)$ |
|---:|---:|---:|---:|---:|
| $13$ | $14$ | $4$ | $17$ | $25$ |
| $73$ | $74$ | $4$ | $79$ | $121$ |

The non-$d(w)=4$ row $q=23$ remains an explicit unresolved branch target:

| $q$ | $w$ | $d(w)$ | $q^+$ |
|---:|---:|---:|---:|
| $23$ | $25$ | $3$ | $29$ |

## Current Catalog Obstruction

The committed catalog at
[`../../output/gwr_dni_gap_type_catalog_details.csv`](../../output/gwr_dni_gap_type_catalog_details.csv)
contains `81,569` rows. Its observed winner classes include many non-$4$
branches, and its $d(w)=4$ surface contains `60,726` rows.

On that surface, reduced $d(w)=4$ type keys are not boundary selectors. For
example, `o4_d4_a1_even_semiprime` maps to multiple exact gap widths, including
`4`, `6`, `10`, `16`, `12`, `24`, `18`, `22`, `30`, and `28` among its most
common observed targets. The exact selector therefore cannot be the existing
reduced type plus the NLSC ceiling.

## Remaining Milestone 2 Requirement

Milestone 2 is not complete. The unmet requirement is the exact d=4 branch law:

$$B_4(q,S,w)=q^+.$$

The current code proves only that the validation row is inside the NLSC horizon.
It does not yet derive $\Delta=q^+-q$ from rulebook state. The next
highest-leverage step is to replace explicit boundary-offset state on the
$d(w)=4$ rows with the smallest measured state ingredient that selects the same
boundary inside $(w,S_{+}(w)]$.

The nearest existing branch fact is the square-residue dead zone recorded in
[`../findings/d4_square_residue_dead_zone.md`](../findings/d4_square_residue_dead_zone.md):
after the floor package $q^+=S_{+}(w)-2$ fails on the live earliest-$d=4$
semiprime branch, $S_{+}(w)-4$ is wheel-forbidden, and the first admissible
non-floor margin splits by $S_{+}(w) \bmod 30$. That fact narrows the branch,
but it still does not select the deeper tail boundary in every row.
