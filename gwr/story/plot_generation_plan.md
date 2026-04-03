# GWR Story Plot Generation Plan

This note ties each story figure to the exact data surface and question it is
meant to answer.

## Figure Set

### `figure_01_exemplar_gap_profiles`

Question:

What does the raw-`Z` landscape inside an individual prime gap actually look
like, and where does the `GWR` winner sit?

Data:

- exact `10^6` surface for short and medium gaps,
- even-window `10^9` surface for a larger-scale exemplar.

### `figure_02_match_rate_surface`

Question:

How far has the zero-counterexample identity between raw-`Z` winners and `GWR`
winners been validated?

Data:

- committed legacy validation JSON,
- repo-native revalidation summary JSON.

### `figure_03_divisor_enrichment`

Question:

Which divisor-count classes are over-selected as winners relative to their
baseline availability?

Data:

- even-window `10^9` surface.

### `figure_04_normalized_position`

Question:

How concentrated are winners near the left side of a gap compared with the
interior baseline?

Data:

- even-window `10^9` surface.

### `figure_05_edge_distance`

Question:

How strongly are winners concentrated near the edges, especially at
edge-distance `2`?

Data:

- even-window `10^9` surface.

### `figure_06_counterexample_pair`

Question:

Why does the unrestricted global theorem fail even though `GWR` still holds?

Data:

- explicit unordered counterexample pair `49` versus `6`.

### `figure_07_winner_heatmap`

Question:

Where do winners live jointly in normalized gap position and divisor-count
space?

Data:

- even-window `10^9` surface.
