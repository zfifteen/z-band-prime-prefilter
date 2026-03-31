---
title: "The Geodesic Prime Prefilter"
subtitle: "Technical Note on Fixed-Point Collapse, Deterministic Factor-Gated Filtering, Candidate-Loop Screening, and RSA Key Generation Acceleration"
author: "Dionisio Alberto Lopez III"
date: "March 31, 2026"
documentclass: article
fontsize: 11pt
geometry: margin=1in
numbersections: true
bibliography: references.bib
link-citations: true
colorlinks: true
abstract: |
  The Geodesic Prime Prefilter is a deterministic cryptographic prime prefilter derived from the fixed-point traversal rate $v = e^2 / 2$ of the divisor-curvature normalization $Z(n) = n / \exp(v \cdot \kappa(n))$ with $\kappa(n) = d(n)\ln(n) / e^2$. At that rate the exact closed form becomes $Z(n) = n^{1 - d(n)/2}$, so confirmed primes collapse to the invariant band $Z = 1.0$ and composites contract below that band. Validation in this repository shows `29/29` calibration primes on the fixed-point band, `0` composite false fixed points, and an exact-calibration curvature separation ratio of `4.54x` on the tractable corpus. The production Python path then replaces exact divisor counting with a deterministic factor-gated surrogate that preserves the fixed-point survivor convention before fixed-base Miller-Rabin and final `sympy.isprime` confirmation. The curated repo benchmark summary reports `91.02%` and `91.41%` candidate rejection before Miller-Rabin on `2048`-bit and `4096`-bit corpora, candidate-loop speedups of `2.95x` and `3.33x`, and end-to-end deterministic RSA key-generation speedups of `2.09x` over `300` `2048`-bit keypairs and `2.82x` over `50` `4096`-bit keypairs while reducing Miller-Rabin work by `90.97%` to `91.07%`. The repository therefore establishes a mathematically derived fixed-point law, a deterministic production prefilter built from it, and a measured cryptographic payoff in the tested Python regime.
---

**Keywords:** divisor count; fixed-point collapse; prime generation; Miller-Rabin prefilter; deterministic screening; RSA key generation

# Opening Statement

The Geodesic Prime Prefilter is a deterministic cryptographic prefilter derived from a fixed-point law in divisor-curvature normalization [@geodesicprimeprefilter2026].

At the distinguished traversal rate `v = e^2 / 2`, the exact normalization sends every prime to the invariant band `Z = 1.0` and pushes composites below that band.

The repository now establishes a concrete result set:

- the exact fixed-point law holds numerically on the tractable calibration corpus,
- the production path preserves that law as its survivor convention rather than as a loose metaphor,
- candidate-loop screening removes about ninety-one percent of tested cryptographic candidates before Miller-Rabin,
- and the current Python implementation yields measured end-to-end RSA key-generation gains on deterministic streams.

# Core Proposal

The narrowest claim in this repository begins with three arithmetic ingredients:

$$
d(n), \qquad \kappa(n) = \frac{d(n)\ln(n)}{e^2}, \qquad Z(n) = \frac{n}{\exp(v \cdot \kappa(n))}.
$$

Here `d(n)` is the divisor count, `\kappa(n)` is the divisor-curvature load, and `Z(n)` is the curvature-weighted normalization.

At the distinguished fixed-point traversal rate

$$
v = \frac{e^2}{2},
$$

the normalization collapses to the exact closed form

$$
Z(n) = n^{1 - d(n)/2}.
$$

That identity has immediate arithmetic consequences:

- if `n` is prime, then `d(n) = 2` and `Z(n) = 1`,
- if `n` is semiprime with two distinct prime factors, then `d(n) = 4` and `Z(n) = 1/n`,
- if `n` is composite in general, then `d(n) > 2` and `Z(n) < 1`.

The core reading is therefore:

> divisor structure and logarithmic scale determine a traversal rate at which primes occupy a fixed-point band and composites contract below it.

This note is about what the repository establishes when that law is turned into a deterministic prime-screening pipeline.

# Why This Matters Computationally

The computational use of the fixed-point law is narrower and stronger than a new way to describe integers.

1. It provides an exact invariant target for prime candidates.
2. It separates the mathematical derivation from the runtime production filter without breaking the logic that connects them.
3. It lets the implementation reject many composites before the probable-prime path rather than after it.
4. It yields a deterministic screening front end for prime search inside RSA-style key construction [@rsa1978].

The repo is not presenting the fixed-point law as a standalone primality proof. It is presenting a deterministic structural prefilter whose payoff can be measured on the same candidate streams and the same final confirmation path.

# Mathematical Core: Fixed-Point Collapse

The divisor-count background belongs to classical multiplicative number theory [@hardywright2008]. The repository uses that arithmetic structure directly rather than replacing it with a generic score.

Start from

$$
\kappa(n) = \frac{d(n)\ln(n)}{e^2}
$$

and

$$
Z(n) = \frac{n}{\exp(v \cdot \kappa(n))}.
$$

Set

$$
v = \frac{e^2}{2}.
$$

Then

$$
\begin{aligned}
Z(n) &= \frac{n}{\exp\left(\frac{e^2}{2} \cdot \frac{d(n)\ln(n)}{e^2}\right)} \\
&= \frac{n}{\exp\left(\frac{d(n)}{2}\ln(n)\right)} \\
&= \frac{n}{n^{d(n)/2}} \\
&= n^{1 - d(n)/2}.
\end{aligned}
$$

That is the exact fixed-point collapse.

The tractable calibration corpus in the repo shows:

- `29/29` calibration primes on the numeric band `Z = 1.0`,
- `0` composite false fixed points,
- prime mean `\kappa = 3.6883`,
- composite mean `\kappa = 16.7545`,
- separation ratio `4.54x`.

On that same `20`-bit calibration corpus, fixed-base Miller-Rabin matches exact primality with `100%` accuracy in the committed benchmark report.

The narrow supported claim is therefore exact and local:

> under exact divisor counting, the fixed-point law is algebraically exact and numerically clean on the tractable calibration regime tested in this repository.

# Operational Evidence in the Exact Setting

The exact fixed-point law is the derivation surface and the calibration oracle. It is not the cryptographic runtime path.

The boundary is explicit in the benchmark artifacts. Exact divisor counting still uses `O(sqrt n)` enumeration in the current executable path. For arbitrary `2048`-bit candidates, the benchmark report describes the implied worst-case trial space as about `2^1024` divisibility checks per candidate.

That scale boundary is useful rather than damaging. It cleanly separates two jobs:

- the exact path establishes the law and the calibration band,
- the production path exploits that law without pretending exact divisor counting is the right runtime mechanism at cryptographic scale.

The same calibration corpus shows that the deterministic proxy still preserves the fixed-point reading operationally. On the committed small-panel proxy calibration, it hits `29` fixed points with `0` composite false fixed points and `100%` classification accuracy.

So the exact regime is doing more than symbolic derivation. It anchors the invariant target that the production filter is built to preserve.

# From Exact Fixed-Point Law to Deterministic Production Filter

The runtime pipeline in this repository is intentionally narrow.

1. Generate deterministic odd candidates from a SHA-256 namespace/index stream.
2. Scan the candidate against factor-gated prime tables in primary, tail, and deep-tail intervals.
3. Reject immediately only when a concrete factor is found.
4. Keep survivors on the band convention `proxy_z = 1.0`.
5. Run fixed-base Miller-Rabin on survivors.
6. Apply final `sympy.isprime` confirmation in the current Python implementation.

This is not a heuristic score that floats independently of the contract. It is a deterministic prefilter that treats the fixed-point band as the survivor convention and concrete factor discovery as the rejection trigger.

The contract surface is equally narrow:

- `spec/contract.md` fixes the deterministic behavior,
- `spec/vectors/` commits the candidate stream, prefilter decisions, fixed-point checks, and prime-generation vectors,
- Python is the initial normative executable implementation,
- future Java and Apple-Silicon C ports are required to match that same parity surface before any reference-status claim changes.

The engineering reading is straightforward. The exact fixed-point law supplies the invariant. The production path keeps one deterministic execution flow that respects that invariant while moving the expensive work farther down the pipeline.

# Candidate-Loop Screening and RSA Key Generation

The cryptographic screening result appears at two levels.

The first is the candidate loop itself. In the curated repo benchmark summary:

- the `2048`-bit control corpus rejects `91.02%` of candidates before Miller-Rabin and reports `2.95x` pipeline speedup,
- the `4096`-bit control corpus rejects `91.41%` of candidates before Miller-Rabin and reports `3.33x` pipeline speedup.

That is already a strong screening result. Most candidates never reach the probable-prime path.

The second level is end-to-end deterministic RSA key generation, which is the more operational test [@rsa1978].

For `300` deterministic `2048`-bit keypairs, the committed benchmark summary reports:

- baseline `291938.126792` ms,
- accelerated `139942.831833` ms,
- speedup `2.09x`,
- Miller-Rabin reduction `90.97%`.

For `50` deterministic `4096`-bit keypairs, the same summary reports:

- baseline `757750.922792` ms,
- accelerated `268557.631625` ms,
- speedup `2.82x`,
- Miller-Rabin reduction `91.07%`.

The benchmark harness also requires the baseline and accelerated paths to produce identical deterministic keypairs. So the measured gain is not coming from a different candidate stream or a looser acceptance contract. It comes from screening away composite work earlier on the same deterministic search.

# What The Repo Establishes

The repository now establishes the following results.

1. The divisor-curvature normalization has a distinguished fixed-point traversal rate `v = e^2 / 2` at which the exact closed form becomes `Z(n) = n^{1 - d(n)/2}`.
2. Under exact divisor counting on the tractable calibration corpus, confirmed primes lie on `Z = 1.0`, composites contract below that band, and the observed curvature separation ratio is `4.54x`.
3. The production Python path converts that fixed-point law into a deterministic factor-gated prefilter with one narrow survivor convention and one narrow rejection rule.
4. On the committed cryptographic candidate corpora, the prefilter removes about `91%` of candidates before Miller-Rabin and yields about threefold candidate-loop speedup in the curated summary surface.
5. On deterministic RSA key generation, the current Python implementation achieves `2.09x` speedup at `2048` bits and `2.82x` speedup at `4096` bits while cutting Miller-Rabin work by `90.97%` to `91.07%`.
6. The contract, vectors, tests, and benchmark artifacts make the result reproducible and portable across future implementations.

That is a larger result set than a derivation note alone and a stronger result set than a benchmark table with no mathematical anchor.

# Limits And Scope

The current note is strong on the tested Python regime and narrow about what it does not claim.

- The fixed-point law is exact, but the executable exact divisor-count path is only practical on the small calibration regime.
- The production prefilter is not a primality proof. Survivors still require Miller-Rabin and final confirmation.
- The current production filter rejects only when one of the gated prime tables finds a concrete factor. It does not claim universal optimality over all possible deterministic screening tables.
- The validated implementation surface is Python. Java and Apple-Silicon C ports are planned in the repo architecture but are not yet parity-complete.
- The note does not claim that the current benchmark settings exhaust the performance envelope across all bit sizes, machines, or table configurations.

Those are real scope limits, but they do not weaken the established fixed-point law or the measured production gains inside the regime the repository actually tests.

# Practical Interpretation

The practical use of the Geodesic Prime Prefilter is not “replace primality testing.”

The practical use is:

- use the exact fixed-point law as the derivation and audit surface,
- use the deterministic factor-gated surrogate as the runtime screen,
- preserve the fixed-point band as the invariant survivor target,
- and reduce probable-prime workload without changing the deterministic candidate stream or the final confirmation semantics.

In the current repository, that means the mathematical law and the engineering path stay connected. The prefilter is not merely inspired by the fixed-point collapse. It is structured around it.

That makes the artifact useful both as research code and as a foundation for future ports. Its behavior is compact enough to audit, explicit enough to reproduce, and narrow enough to defend.

# Open Technical Targets

The strongest next steps are:

1. bring the planned Java implementation to committed vector parity,
2. bring the planned Apple-Silicon C99/GMP/MPFR implementation to vector parity and manual benchmark parity,
3. broaden the benchmark surface beyond the current `2048`-bit and `4096`-bit deterministic corpora,
4. map screening efficiency more explicitly as a function of prime-table limits, chunk sizes, and deep-tail thresholds,
5. tighten the analytic number-theory side of the contraction story beyond the current small-panel exact calibration.

# Conclusion

The narrow mathematical heart of the project is the fixed-point collapse

$$
Z(n) = n^{1 - d(n)/2}
$$

at the traversal rate

$$
v = \frac{e^2}{2}.
$$

The repository now establishes a broader operational result set around that core. The exact law is real on the tractable calibration corpus. The production path turns that law into a deterministic factor-gated prefilter. The tested Python implementation then converts that screening advantage into measured end-to-end RSA key-generation gains on deterministic streams.

That is a strong place for the project to be. The Geodesic Prime Prefilter now stands as a mathematically derived fixed-point law, a deterministic production filter built from that law, and a measured cryptographic acceleration artifact in the regime the repository has validated.

# Artifact References

- [Repository README](../README.md)
- [Benchmark Summary](../docs/benchmarks.md)
- [Architecture Note](../docs/architecture.md)
- [Contract](../spec/contract.md)
- [Benchmark Report](../benchmarks/output/python/BENCHMARK_REPORT.md)
- [Manual Validation](../docs/manual_validation.md)
- [Python Implementation](../src/python/geodesic_prime_prefilter/prefilter.py)
