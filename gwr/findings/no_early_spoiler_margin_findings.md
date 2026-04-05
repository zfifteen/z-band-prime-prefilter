# No-Early-Spoiler Margin Findings

This note records the executed exact margin scan from
[`no_early_spoiler_margin_scan.py`](../experiments/proof/no_early_spoiler_margin_scan.py).

The target is the actual unresolved universal step behind `GWR`:

for the true gap carrier

$$
m^* = \min\{m \in G : d(m) = d_{\min}\},
$$

does every earlier interior composite $k < m^*$ satisfy

$$
L(k) < L(m^*)?
$$

The ordered-dominance theorem already removes every later candidate. This scan
measures the exact slack against the true `GWR` carrier itself.

## Recorded Margins

For every earlier candidate $k < m^*$, the scan records two equivalent positive
quantities:

1. the direct log-score margin

$$
L(m^*) - L(k),
$$

2. the critical-ratio margin

$$
\frac{d(k) - 2}{d_{\min} - 2} - \frac{\ln m^*}{\ln k}.
$$

The second quantity is the direct slack in the exact spoiler condition

$$
L(k) \ge L(m^*)
\iff
\frac{\ln m^*}{\ln k} \ge \frac{d(k) - 2}{d_{\min} - 2}.
$$

So a positive critical-ratio margin means the earlier composite is still safely
below spoiler threshold.

## Current Executed Artifact

- [`no_early_spoiler_margin_scan_2e7.json`](../../output/gwr_proof/no_early_spoiler_margin_scan_2e7.json)

## Strongest Supported Result

On the full exact surface through $2 \cdot 10^7$:

- `1163198` prime gaps with composite interior,
- `3349874` earlier interior candidates before the true `GWR` carrier,
- `0` exact earlier spoilers against that carrier.

So on the current exact surface, the no-early-spoiler condition itself holds
with zero counterexamples.

The scan also records the current tightest margins on that surface:

- smallest direct log-score margin:
  $$
  L(m^*) - L(k) \approx 0.9808292530
  $$
  at the gap $(7, 11)$ with earlier candidate $8$ and winner $9$;
- smallest critical-ratio margin:
  $$
  \frac{d(k) - 2}{d_{\min} - 2} - \frac{\ln m^*}{\ln k}
  \approx 0.0714285168
  $$
  at the gap $(2486509, 2486513)$ with earlier candidate
  $2486510$, winner $2486512$, winner class $d_{\min}=30$, and earlier class
  $d=32$.

So the smallest direct score slack and the smallest ratio-form slack come from
different regimes. The tiny-gap edge case controls the direct score minimum,
while the tightest ratio cases move into higher divisor classes where the
critical ratio lies much closer to $1$.

## What This Adds Beyond The Local-Dominator Scan

The earlier local-dominator artifact already showed that every earlier
candidate eventually loses to some later admissible composite.

This margin scan is stronger in the direction that matters for `GWR`:

- it compares every earlier candidate directly to the actual winner carrier
  $m^*$,
- it records the tightest direct log-score slack,
- and it records the tightest critical-ratio slack in the exact spoiler
  inequality.

So this is the current exact measurement surface for the no-early-spoiler
condition itself, not just for later admissible rescue.

## Current Reading

The strongest supported claim from this artifact is:

on the exact through-$2 \cdot 10^7$ surface, every earlier higher-divisor
candidate is already beaten by the actual leftmost minimum-divisor carrier, and
the scan records the tightest direct and ratio-form safety margins for that
fact.

This does not by itself make `GWR` a universal theorem.
It does tighten the open problem to one precise remaining task:

turn these exact no-early-spoiler margins into a general argument that holds in
every prime gap.
