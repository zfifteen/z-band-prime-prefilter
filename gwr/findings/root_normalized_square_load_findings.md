# Root-Normalized Square Load Carries `d=4` Handoff Memory

This note records a new `d=4` handoff finding on the committed gap-type
catalog surface.

The strongest supported result is:

current winner parity is not the live explanatory variable once current local
`d=4` geometry is fixed. The durable handoff variable is a pair:

- previous reduced state, and
- a root-normalized square-threat load carried by the current gap.

The current load is

$$L_{\square}(w, q) = \sqrt{w}\,\frac{q-w}{S_{+}(w)-w},$$

where:

- $w$ is the current `d=4` winner,
- $q$ is the right-end prime of that same gap,
- and $S_{+}(w)$ is the next prime square after $w$.

This is a direct reweighting of the existing square-phase utilization
$U_{\square}(w, q) = (q-w)/(S_{+}(w)-w)$ by the square-root scale of the
winner.

## Probe Surface

Artifacts:

- runner:
  [`../../benchmarks/python/predictor/gwr_root_normalized_square_load_probe.py`](../../benchmarks/python/predictor/gwr_root_normalized_square_load_probe.py)
- tests:
  [`../../tests/python/predictor/test_gwr_root_normalized_square_load_probe.py`](../../tests/python/predictor/test_gwr_root_normalized_square_load_probe.py)
- summary JSON:
  [`../../output/gwr_root_normalized_square_load_summary.json`](../../output/gwr_root_normalized_square_load_summary.json)
- cell CSV:
  [`../../output/gwr_root_normalized_square_load_cells.csv`](../../output/gwr_root_normalized_square_load_cells.csv)

The probe reads the already-committed gap-type catalog detail CSV, keeps only
transitions whose current gap has `d=4` winner, and scores one-step next-triad
prediction on two deterministic surfaces:

- exact baseline through `current_right_prime <= 10^6`,
- pooled sampled windows from `10^12` through `10^18`.

## Cross-Regime Observable Fact

The raw square-phase median collapses almost completely across the two tested
regimes:

- exact `<=10^6` median raw utilization: `2.3310e-3`,
- sampled `10^12..10^18` median raw utilization: `7.9420e-8`,
- sampled-to-baseline median ratio: `3.4071e-5`.

So the raw boundary fraction by itself is disappearing rapidly with scale.

The root-normalized load does **not** disappear in the same way:

- exact `<=10^6` median root-normalized load: `1.3687`,
- sampled `10^12..10^18` median root-normalized load: `2.9998`,
- sampled-to-baseline median ratio: `2.1919`.

So the square threat still occupies the same order of magnitude after the
square-root reweighting, even while the raw utilization collapses by about
four and a half orders of magnitude.

## Width/Open Baseline

First score the current `d=4` transition surface against the coarse baseline

- current gap width,
- current first-open offset.

Then add candidate hidden variables.

### Exact `<=10^6`

Gain over the width/open baseline:

| Candidate context | Gain |
|---|---:|
| current winner parity | `0.0010` |
| current carrier family | `0.0010` |
| previous reduced state | `0.0070` |
| root-load band | `0.0020` |
| previous reduced state + root-load band | `0.0191` |
| parity + previous reduced state | `0.0120` |
| parity + previous reduced state + root-load band | `0.0293` |

### Sampled `10^12..10^18`

Gain over the same width/open baseline:

| Candidate context | Gain |
|---|---:|
| current winner parity | `0.0162` |
| current carrier family | `0.0162` |
| previous reduced state | `0.0947` |
| root-load band | `0.0445` |
| previous reduced state + root-load band | `0.1369` |
| parity + previous reduced state | `0.1071` |
| parity + previous reduced state + root-load band | `0.1432` |

So under the coarse width/open baseline, parity still helps a little. But the
larger move is not parity alone. The larger move is previous reduced state plus
the root-load band.

## Local-Geometry Baseline

Now fix the current local `d=4` geometry directly:

- current carrier family,
- current peak offset,
- current first-open offset.

This is the cleaner explanatory test because parity can no longer borrow
information from family or local placement.

### Exact `<=10^6`

Gain over the local-geometry baseline:

| Candidate context | Gain |
|---|---:|
| current winner parity | `0.0000` |
| previous reduced state | `0.0037` |
| root-load band | `0.0012` |
| previous reduced state + root-load band | `0.0122` |

### Sampled `10^12..10^18`

Gain over the same local-geometry baseline:

| Candidate context | Gain |
|---|---:|
| current winner parity | `0.0000` |
| previous reduced state | `0.0588` |
| root-load band | `0.0312` |
| previous reduced state + root-load band | `0.1219` |

This is the decisive readout.

Once the current local `d=4` geometry is held fixed:

- parity contributes zero additional gain on both tested surfaces,
- previous reduced state still contributes,
- root-load band still contributes,
- and the pair `previous reduced state + root-load band` beats either one
  alone.

The incremental gain from adding root-load band on top of previous reduced
state is:

- exact `<=10^6`: `+0.0085`,
- sampled `10^12..10^18`: `+0.0631`.

So the square-threat load is not a small cosmetic adjustment to the discrete
state. It is the larger residual variable, especially on the higher-scale
surface.

## Concrete Cell Example

The aggregate result is not carried by one pooled average alone.

On the exact surface, after the previous state
`o4_higher_divisor_even|5<=d<=16`, the next-triad share changes materially
across current root-load bands:

- `lt1`: `0.6361` on `1,176` rows,
- `1to3`: `0.5581` on `1,041` rows,
- `3to10`: `0.5137` on `658` rows.

So within one fixed previous reduced state, the current root-load band is
already moving the next-step return probability by about twelve percentage
points.

## Reading

This changes the internal interpretation of the recent parity and hidden-state
probes.

The parity probe was not empty. Under the coarser width/open baseline, parity
does carry predictive signal. But the local-geometry readout shows why:

parity is acting as a proxy label for a more concrete current-gap load and the
way that load interacts with previous reduced state.

So the current `d=4` square threat is doing more than bounding the right edge
or giving a same-gap utilization coordinate. After root normalization, it is a
cross-gap memory carrier.

That is the structural change:

- old reading: parity looks like the lightweight hidden state,
- new reading: parity is the coarse proxy, while the live hidden variable is
  previous reduced state modulated by root-normalized square-threat load.

## Decision Rule

For current `d=4` gaps, do not treat current winner parity as the decisive
next-step memory variable once current carrier family, current winner offset,
and current first-open offset are already fixed.

Instead:

1. compute the current root-normalized square load $L_{\square}(w, q)$,
2. place it in the fixed bands `lt1`, `1to3`, `3to10`, `ge10`,
3. forecast next-triad return from the pair
   `(previous reduced state, root-load band)`.

On the current executed surface, that pair beats previous reduced state alone
and root-load band alone on both the exact baseline and the sampled high-scale
windows.

## Scope

This is a bounded handoff finding on the committed catalog surface. It does not
claim a universal theorem for all prime-gap regimes, and it does not claim that
root-normalized square load alone closes the full scheduler problem.

What it does show is narrower and stronger:

after current local `d=4` geometry is fixed, parity disappears as an
independent variable, but root-normalized square-threat load does not.
