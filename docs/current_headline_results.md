# Current Headline Results

- **Unconditional exact DNI/GWR next-prime oracle.** The repository now
  carries an exact next-prime walker in unbounded form. Given a known prime
  `q`, the oracle scans divisor counts to the right until the first prime
  boundary, takes the lexicographic minimum over the composite interior, and
  recovers the next prime by the witness map. That mechanism is exact by
  construction at any scale. See
  [./research/predictor/gwr_dni_exact_recursive_prime_walk_note.md](./research/predictor/gwr_dni_exact_recursive_prime_walk_note.md).
- **Dynamic bounded walker replaces the falsified fixed theorem.** The old
  fixed map `{2:44, 4:60, 6:60}` is false. It fails at `q = 24,098,209`,
  where the square branch gives `E(q) = 72 > 60`. The current bounded walker
  uses `C(q) = max(64, ceil(0.5 * log(q)^2))`. The square-branch audit through
  `p <= 10^6` tested `78,498` prime squares, found `7,477` fixed-map
  violations, and observed maximum square offset `246`. See
  [../benchmarks/python/predictor/square_branch_gap_audit.py](../benchmarks/python/predictor/square_branch_gap_audit.py)
  and
  [../benchmarks/python/predictor/gwr_dni_recursive_walk.py](../benchmarks/python/predictor/gwr_dni_recursive_walk.py).
- **Verified recursive walk surface.** On the combined exact $10^6 + 10^7$
  next-gap surface, the DNI transition rule is exact on
  `743,075 / 743,075` rows. The recursive walk records
  `664,578 / 664,578` exact consecutive next-prime recoveries from prime `11`
  through prime `10,000,121` with `0` skipped gaps, and the sampled decade
  ladder from $10^2$ through $10^18$ stayed at exact hit rate `1.0` with `0`
  skipped gaps across `860` measured recursive steps. See
  [./research/predictor/gwr_dni_exact_recursive_prime_walk_note.md](./research/predictor/gwr_dni_exact_recursive_prime_walk_note.md).
- **Built-in falsification instrument.** The predictor walker now ships with a
  compare mode that runs the bounded and unbounded walkers in lockstep and
  records any bounded miss immediately. See
  [../benchmarks/python/predictor/gwr_dni_recursive_walk.py](../benchmarks/python/predictor/gwr_dni_recursive_walk.py).
- **Formal theorem statement.** The current headline theorem is
  [../gwr/findings/gwr_hierarchical_local_dominator_theorem.md](../gwr/findings/gwr_hierarchical_local_dominator_theorem.md).
  It states the winner law directly in hierarchical first-arrival and
  local-dominator form.
- **Exact full left-flank scan through $2 \times 10^7$.** The committed
  artifact
  [../output/gwr_proof/earlier_spoiler_local_dominator_scan_2e7.json](../output/gwr_proof/earlier_spoiler_local_dominator_scan_2e7.json)
  reports `1,163,198` gaps, `3,349,874` earlier candidates, and `0`
  unresolved.
- **Exact no-early-spoiler surface through $2 \times 10^7$.** The committed
  artifact
  [../output/gwr_proof/no_early_spoiler_margin_scan_2e7.json](../output/gwr_proof/no_early_spoiler_margin_scan_2e7.json)
  reports `1,163,198` gaps, `3,349,874` earlier candidates before the true
  `GWR` carrier, and `0` exact earlier spoilers. The companion artifacts
  [../output/gwr_proof/no_early_spoiler_ratio_frontier_2e7.json](../output/gwr_proof/no_early_spoiler_ratio_frontier_2e7.json),
  [../output/gwr_proof/large_gap_margin_scan_2e7.json](../output/gwr_proof/large_gap_margin_scan_2e7.json),
  and
  [../output/gwr_proof/asymptotic_bridge_load_scan_2e7.json](../output/gwr_proof/asymptotic_bridge_load_scan_2e7.json)
  record the exact pair frontier, large-gap companion surface, and normalized
  bridge-load surface for the same no-early-spoiler condition.
- **Square-adjacent stress test at $10^{12}$.** The matched pre-square and
  post-square artifact
  [../output/gwr_proof/earlier_spoiler_local_dominator_scan_square_adjacent_1e12.json](../output/gwr_proof/earlier_spoiler_local_dominator_scan_square_adjacent_1e12.json)
  reports `137,771` gaps, `649,769` earlier candidates, and `0` unresolved.
- **Current proof bridge status.** The note
  [../gwr/experiments/proof/proof_bridge_universal_lemma.md](../gwr/experiments/proof/proof_bridge_universal_lemma.md)
  isolates the remaining large-$p$ bridge as an explicit-constant task, and
  the helper
  [../gwr/experiments/proof/proof_bridge_certificate.py](../gwr/experiments/proof/proof_bridge_certificate.py)
  checks concrete gap-bound and divisor-growth parameter choices against the
  exact finite base already committed in the repo. The current proof-facing
  status is therefore: exact finite base through $2 \times 10^7$, explicit
  normalized bridge target identified, universal closure still dependent on
  chosen effective constants.
- **No-Later-Simpler-Composite condition.** Once the implemented winner
  appears inside a tested prime gap, the next prime arrives before any later
  interior composite with strictly smaller divisor count. The dedicated closure
  study reports zero observed violations on a deterministic even-band ladder at
  every decade from $10^8$ through $10^{18}$. See the
  [../gwr/findings/no_later_simpler_composite_theorem.md](../gwr/findings/no_later_simpler_composite_theorem.md)
  and the
  [../gwr/findings/closure_constraint_findings.md](../gwr/findings/closure_constraint_findings.md).
- **Dominant $d=4$ reduction.** In the dominant winner regime, the tested gaps
  admit no interior prime square, and the implemented winner is exactly the
  first interior carrier with $d(n)=4$. This holds on exact full scans at
  $10^6$ and $2 \times 10^7$ and on the deterministic even-band ladder through
  $10^{18}$, while the stricter semiprime-only wording is explicitly falsified
  by a thin prime-cube exception family. See the
  [../gwr/findings/dominant_d4_arrival_reduction_findings.md](../gwr/findings/dominant_d4_arrival_reduction_findings.md)
  and the
  [../gwr/findings/square_exclusion_first_d4_theorem.md](../gwr/findings/square_exclusion_first_d4_theorem.md).
- **Deterministic prefilter performance.** The current production Python path
  rejects about $91\%$ of tested odd candidates before Miller-Rabin and
  produced $2.09\times$ and $2.82\times$ end-to-end deterministic RSA
  key-generation speedups on the curated $2048$-bit and $4096$-bit benchmark
  corpora. See [./prefilter/benchmarks.md](./prefilter/benchmarks.md).
