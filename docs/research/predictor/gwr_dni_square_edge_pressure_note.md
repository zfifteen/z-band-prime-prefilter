# Square-Edge Pressure In The DNI Cutoff Tail

The strongest new fact from the current square-branch surface is this:

the dangerous rows are not generic large-gap rows. They are late-square rows.

On the direct square scan through `p <= 10^7`, only `17.1429%` of tested prime
squares land in the rightmost quarter of their enclosing prime gap. But in the
top `0.1%` cutoff-utilization tail, that share jumps to `91.1411%`.

So the current bounded tail is not being driven mainly by gaps whose full width
nearly reaches the dynamic cutoff. It is being driven by prime squares that
arrive very late inside the gap that contains them.

## 1. Observable Facts

The new probe is:

- [`../../../benchmarks/python/predictor/gwr_dni_square_edge_pressure_probe.py`](../../../benchmarks/python/predictor/gwr_dni_square_edge_pressure_probe.py)

Its retained artifacts are:

- [`../../../output/gwr_proof/square_edge_pressure_probe_1e7/gwr_dni_square_edge_pressure_probe_summary.json`](../../../output/gwr_proof/square_edge_pressure_probe_1e7/gwr_dni_square_edge_pressure_probe_summary.json)
- [`../../../output/gwr_proof/square_edge_pressure_probe_1e7/gwr_dni_square_edge_pressure_probe_frontier.csv`](../../../output/gwr_proof/square_edge_pressure_probe_1e7/gwr_dni_square_edge_pressure_probe_frontier.csv)

The direct scan tests every odd prime square with `3 <= p <= 10^7` and, for
each row, measures:

- the square offset `p^2 - prevprime(p^2)`,
- the full enclosing gap width,
- the square's left-share inside that gap,
- the gap-width fraction of the dynamic cutoff,
- the square-offset fraction of the dynamic cutoff.

The summary numbers are:

- tested square rows: `664,578`,
- mean left-share: `0.4538440663687442`,
- baseline share with left-share `>= 0.75`: `0.1714290873306068`,
- baseline share with gap-width / cutoff `>= 0.75`: `0.00007222628495075071`.

In the top utilization tails:

| tail | mean left-share | left-share `>= 0.75` | mean gap-width / cutoff | gap-width / cutoff `>= 0.75` |
|---|---:|---:|---:|---:|
| top `10%` | `0.7609651316505601` | `0.5944153735113678` | `0.2742375630156846` | `0.0006315409599422591` |
| top `1%` | `0.8359394630862456` | `0.791904905206139` | `0.41189725976175445` | `0.004814926271441469` |
| top `0.1%` | `0.8746618769326594` | `0.9114114114114115` | `0.5494698753706281` | `0.02702702702702703` |

Those numbers matter together.

Even in the top `0.1%` utilization tail, the full gap width is usually nowhere
near the cutoff. But the square is very often in the rightmost quarter of the
gap.

## 2. Why This Is Not The Standard Story

The closest existing ideas in the repository are:

1. the dynamic cutoff law
   $$C(q) = \max(64, \lceil 0.5 \log(q)^2 \rceil);$$
2. the mixed-scale cutoff note, which says the square branch carries the
   visible `log(q)^2` pressure;
3. the raw gap-ridge notes, which say the usual raw-`Z` winner is near an edge
   and is usually a `d(n)=4` carrier.

This note overlaps with all three, but it is making a different claim.

The difference is that this note is not about which branch is expensive. It is
about which square rows inside that branch are expensive.

The measured tail is selecting an orientation:

- not simply large enclosing gaps,
- not simply prime squares anywhere inside those gaps,
- but prime squares that land very late inside the gap.

That is a structural filter on the square branch, not just a scale statement.

## 3. Candidate Mechanism

On the square branch, the utilization is

$$\frac{\text{square offset}}{C(q)} = \frac{\text{gap width}}{C(q)} \times \frac{\text{square offset}}{\text{gap width}}.$$

If whole-gap size were the main driver, then the top utilization tail would be
dominated by rows whose full gap width already sits close to the cutoff.

That is not what the measured surface shows.

The top tail has strong late-square concentration even when the full gap width
is still far below the cutoff. So the dangerous event is a two-factor event:

- the gap must be wide enough to matter,
- and the prime square must land unusually close to the right boundary.

The second factor is doing visible work.

## 4. Out-Of-Sample Check On The Existing `10^8` Frontier

The retained square-branch frontier through `p <= 10^8` is still:

- [`../../../output/gwr_proof/square_branch_dynamic_cutoff_search_1e8/square_branch_dynamic_cutoff_search_frontier.csv`](../../../output/gwr_proof/square_branch_dynamic_cutoff_search_1e8/square_branch_dynamic_cutoff_search_frontier.csv)

Its four frontier rows with utilization above `0.6` have left-shares:

- `p = 509`: `0.7272727272727273`
- `p = 3929`: `0.8909090909090909`
- `p = 6,424,279`: `0.9574468085106383`
- `p = 33,701,407`: `0.8168498168498168`
- `p = 82,357,433`: `0.8598726114649682`

So the late-square geometry survives beyond the `10^7` calibration range.

## 5. Core Insight

The live cutoff tail should be treated as a square-edge pressure problem.

That is narrower than "square branch dominates" and sharper than "large gaps
matter." The measured tail is saying:

- the dangerous rows are mostly not full-gap-near-cutoff rows,
- they are rows where the prime square lands late inside the gap,
- and the late landing is the visible discriminator.

This also means the square-tail geometry is oriented differently from the
repository's usual raw-`Z` near-edge ridge, which is typically carried by
earlier `d(n)=4` winners.

## 6. Falsifiable Prediction

The prediction is:

on future direct square scans, new overall utilization records should continue
to come from rows with left-share at least `0.75`.

Equivalently, the rightmost quarter of the enclosing gap should continue to act
as the live pressure zone for new square-branch records.

This note would be seriously weakened by either of these:

1. a new overall square-branch utilization record with left-share `< 0.75`;
2. a larger direct square scan in which the top `0.1%` utilization tail no
   longer shows strong enrichment for left-share `>= 0.75`.

## 7. Decision Rule

For future bounded-cutoff audits:

- do not use whole-gap width alone as the first risk proxy for the square
  branch;
- classify square rows by left-share before changing the global cutoff law;
- prioritize direct search on rows whose square lies in the rightmost quarter
  of the enclosing gap.

That is the smaller deterministic search surface that the current data is
actually pointing to.
