# GWR Experiments

This directory tracks the executable and artifact surface for the `Gap Winner
Rule`.

## Proof Pursuit

- [`proof/`](./proof/):
  scripts and artifacts for the universal bridge closure, including the
  committed explicit-constant certificate against the $2 \cdot 10^7$ finite
  base.

## Current Validation Entry Points

- [`benchmarks/python/gap_ridge/lexicographic_peak_validation.py`](../../benchmarks/python/gap_ridge/lexicographic_peak_validation.py)
  Legacy validation script for the committed tested surface.
- [`benchmarks/python/gap_ridge/lexicographic_rule_revalidation.py`](../../benchmarks/python/gap_ridge/lexicographic_rule_revalidation.py)
  Extended revalidation script with explicit winner comparisons, new sampled
  windows, enrichment statistics, and alternative score probes.

## Current Outputs

- [`benchmarks/output/python/gap_ridge/lexicographic_peak_validation/lexicographic_peak_validation.json`](../../benchmarks/output/python/gap_ridge/lexicographic_peak_validation/lexicographic_peak_validation.json)
- [`output/lexicographic_rule_revalidation_summary.json`](../../output/lexicographic_rule_revalidation_summary.json)
- [`output/lexicographic_rule_revalidation_report.md`](../../output/lexicographic_rule_revalidation_report.md)

## Registry

### Baseline committed surface

- exact `10^6`
- exact `10^7`
- sampled even-window ladder from `10^8` through `10^18`

### Extended revalidation surface

- exact `2 * 10^7`
- sampled even-window and seeded-window runs at `10^8`, `10^9`, `10^10`,
  `10^11`, and `10^12`
- enrichment measurement on the `10^9` even-window surface
- alternative score probes on exact `10^6` and sampled `10^9`

## Working Rule

For this subtree, a tested regime validates `GWR` if and only if it contains
zero counterexample gaps where the raw-`Z` winner differs from the
minimum-divisor leftmost winner.
