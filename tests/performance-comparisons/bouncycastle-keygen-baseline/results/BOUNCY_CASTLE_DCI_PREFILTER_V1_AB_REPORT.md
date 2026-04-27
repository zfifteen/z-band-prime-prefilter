# Bouncy Castle DCI Prefilter V1 A/B Report

Date: 2026-04-05

This report compares a fresh paired baseline run of source-built BC `r1rv83` against a source-built BC `r1rv83` build patched with the DCI concrete-factor prefilter inside `BigIntegers.createRandomPrime()`.

This experiment measures the real DCI prefilter path. It does not include the earlier RSA upper-band optimization.

## Headline Result

- Fresh paired baseline total time: `169513.930791` ms
- DCI-prefilter total time: `357409.675121` ms
- Relative speed: `0.474285x` of baseline
- Wall-clock increase: `110.843837%`

## A/B Comparison

| Metric | Fresh baseline | DCI prefilter v1 |
|---|---:|---:|
| Total time (ms) | `169513.930791` | `357409.675121` |
| Mean time (ms) | `1695.139308` | `3574.096751` |
| Median time (ms) | `1497.451958` | `3145.400792` |
| Min time (ms) | `273.659875` | `356.529541` |
| Max time (ms) | `4701.479167` | `10179.802458` |
| Throughput (keypairs/s) | `0.589922` | `0.279791` |

## Setup

- Workload: direct-core `org.bouncycastle.crypto.generators.RSAKeyPairGenerator`
- RSA size: `4096` bits
- Timed iterations: `100`
- Warmup iterations: `0`
- Public exponent: `65537`
- Certainty: `144`
- RNG: `SHA1PRNG`
- Seed bytes: `[42]`
- Build JDK: `openjdk version "25.0.2" 2026-01-20`
- Runtime JDK: `openjdk version "21.0.10" 2026-01-20`

The modified build is a pure `createRandomPrime()` DCI-prefilter patch:

- BC raw candidate construction unchanged
- BC `3..743` small-prime product walk unchanged
- DCI primary ladder: odd primes `> 743` through `200003`
- DCI tail ladder: odd primes `> 200003` through `300007`
- Chunk size: `256`
- No deep tail
- No upper-band logic
- No RSA-local changes
- No later probable-prime or key-validation changes

## Prior Sample-Behavior Result

The prior no-patch sample-behavior probe at [`bcprov-jdk18on-1.83-source-r1rv83-prime-sample-behavior-seed-byte-42.json`](./bcprov-jdk18on-1.83-source-r1rv83-prime-sample-behavior-seed-byte-42.json) found:

- exact helper fidelity to BC for the first `1024` outputs on both `256`-bit and `2048`-bit panels
- `0.0` drift on the recorded coarse outputted-prime metrics after adding this exact DCI ladder at the `createRandomPrime()` surface

## Artifacts

- Fresh paired baseline JSON: [`bcprov-jdk18on-1.83-source-r1rv83-rsa4096-direct-core-seed-byte-42-runs-100-fresh-baseline.json`](./bcprov-jdk18on-1.83-source-r1rv83-rsa4096-direct-core-seed-byte-42-runs-100-fresh-baseline.json)
- DCI-prefilter JSON: [`bcprov-jdk18on-1.83-source-r1rv83-dci-prefilter-v1-rsa4096-direct-core-seed-byte-42-runs-100.json`](./bcprov-jdk18on-1.83-source-r1rv83-dci-prefilter-v1-rsa4096-direct-core-seed-byte-42-runs-100.json)
- Sample-behavior JSON: [`bcprov-jdk18on-1.83-source-r1rv83-prime-sample-behavior-seed-byte-42.json`](./bcprov-jdk18on-1.83-source-r1rv83-prime-sample-behavior-seed-byte-42.json)
