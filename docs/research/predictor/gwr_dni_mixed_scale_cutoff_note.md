# Mixed-Scale Cutoff Separation In The Bounded DNI Walker

The strongest new fact from the current predictor surface is this:

the bounded DNI cutoff is carrying two different mechanisms at once, and only
one of them is visibly pressing on the $\log(q)^2$ scale.

On the measured surface, the square branch still behaves like the hard tail.
The non-square continuation branches do not.

## 1. Observable Facts

The new probe is:

- [`../../../benchmarks/python/predictor/gwr_dni_branch_scale_probe.py`](../../../benchmarks/python/predictor/gwr_dni_branch_scale_probe.py)

and its retained artifact set is:

- [`../../../output/gwr_proof/branch_scale_probe/gwr_dni_branch_scale_probe_summary.json`](../../../output/gwr_proof/branch_scale_probe/gwr_dni_branch_scale_probe_summary.json)
- [`../../../output/gwr_proof/branch_scale_probe/gwr_dni_branch_scale_probe_rows.csv`](../../../output/gwr_proof/branch_scale_probe/gwr_dni_branch_scale_probe_rows.csv)

The probe scans deterministic right-prime windows at
$10^6, 10^7, \ldots, 10^{14}$ with width `20,000`, and direct prime-square
windows in prime-$p$ space at
$10^2, 10^3, \ldots, 10^7$ with the same width.

The measured retained maxima are:

- `d=4` right-prime branch:
  peak offset `50` at `q = 1,000,000,004,501`,
  with normalized peak
  $$50 / \log(q) = 1.809560340968778,$$
  and cutoff utilization `0.13089005235602094`.
- `d=6` right-prime branch:
  peak offset `21` at `q = 10,012,703`,
  with normalized peak
  $$21 / \log(q) = 1.3027808360530602,$$
  and cutoff utilization `0.16153846153846155`.

Those are the largest retained non-square normalized peaks on the new probe.

For the square branch, the existing direct square search remains the sharper
large-scale certificate:

- [`../../../output/gwr_proof/square_branch_dynamic_cutoff_search_1e8/square_branch_dynamic_cutoff_search_summary.json`](../../../output/gwr_proof/square_branch_dynamic_cutoff_search_1e8/square_branch_dynamic_cutoff_search_summary.json)

Its frontier maximum is:

- `p = 82,357,433`,
- `q = 6,782,746,770,348,949`,
- square offset `540`,
- dynamic cutoff `665`,
- cutoff utilization `0.8120300751879699`,
- linear log normalization
  $$540 / \log(q) = 14.813531,$$
- log-squared normalization
  $$540 / \log(q)^2 = 0.406372.$$

So the current measured gap is not subtle.
The square branch is already an order of magnitude larger on the linear-log
scale than the retained non-square continuation maxima.

## 2. Why This Is Not The Standard Story

The closest existing ideas in the repository are:

1. the current dynamic cutoff law
   $$C(q) = \max(64, \lceil 0.5 \log(q)^2 \rceil);$$
2. the dominant `d=4` regime rule:
   no interior prime square, then the first interior `d=4` composite wins;
3. the `d=4` square-ceiling note, which studies the next prime relative to the
   first later prime square above the winner.

This note overlaps with all three, but it is not the same claim.

The sharp difference is that this note is about **scan-depth scaling by branch**.
It says the bounded compression is not one asymptotic tail law.
It is a mixed-scale machine:

- the `d=3` square branch behaves like a sparse record-gap process and is the
  visible source of $\log(q)^2$ pressure;
- the `d=4` and `d=6` continuation branches behave like denser carrier races
  and stay on a much smaller scale on the measured windows.

That is a different mechanism claim, a different normalization, and a
different falsification target.

## 3. Candidate Mechanism

After the `12`-offset prefix, a later lexicographic improvement can happen only
if a simpler composite class appears before the next prime closes the gap.

For `d=4` and `d=6` continuations, the next threatening carriers are drawn
from semiprime and cube lanes, which are much denser than prime squares on the
same scale.

For `d=4` winners in particular, the only strictly simpler composite threat is
`d=3`, and that means a prime square.

So the current global cutoff is paying for two different clocks:

- a square clock,
- and a semiprime-lane clock.

The measured surface says the square clock is the expensive one.

## 4. Core Insight

The bounded DNI walker should be treated as a two-regime compression problem,
not a single-cutoff problem.

The practical implication is not "make the cutoff smaller everywhere."
It is narrower:

- if future bounded misses appear, the first suspect should be the square
  branch, not the generic non-square tail;
- a new overall cutoff record should be expected to arrive with
  `exact_next_dmin = 3`, or with a direct square witness behind it;
- until a clean non-square branch breach appears, increasing the global
  $\log(q)^2$ coefficient is mis-targeted.

## 5. Falsifiable Prediction

The prediction is:

on future exact consecutive-right-prime surfaces and deterministic decade
windows beyond the current probe, new overall records in bounded cutoff
utilization will come from the square branch, while `d=4` and `d=6`
continuation rows will stay below `2 log(q)` in peak offset.

Written as a branch rule:

$$\text{if } d_{\min}(q) \in \{4,6\}, \text{ then } E(q) < 2 \log(q)$$

on the next measured surfaces unless the mixed-scale picture is wrong.

This note would be seriously weakened by either of these:

1. an exact consecutive-right-prime counterexample with `d_min in {4,6}` and
   `E(q) >= 2 log(q)`;
2. a new overall cutoff-utilization record whose exact branch is not `d=3`
   and does not reduce to a square witness.

## 6. Decision Rule

For future bounded-compression work:

- when a bounded-vs-exact mismatch appears, classify the exact branch first;
- if the branch is `d=3`, investigate the square surface before changing the
  global cutoff law;
- do not raise the global $\log(q)^2$ coefficient in response to a non-square
  row unless it first breaks the `2 log(q)` envelope on an exact surface.

## 7. Bottom Line

The live bounded cutoff is still empirical.
But the current measured surface says its pressure is not uniform.

The log-squared term is acting like a square shield.
The non-square continuation lanes are not yet asking for that scale.
