# Geodesic Prime Prefilter

Deterministic cryptographic prime prefiltering locked to the sweet-spot band at `v = e^2 / 2`.

This repository is the standalone production extraction of the geodesic prime prefilter first developed inside [`cognitive-distortion-layer`](https://github.com/zfifteen/cognitive-distortion-layer). The Python implementation ships first. Future Java and Apple-Silicon-only C99/GMP/MPFR ports will match the same contract and golden vectors without reshaping the repo.

## Headline Result

- `2.09x` end-to-end speedup across `300` deterministic `2048`-bit RSA keypairs
- `2.82x` end-to-end speedup across `50` deterministic `4096`-bit RSA keypairs
- `90.97%` to `91.07%` Miller-Rabin reduction with the prime band preserved

These are full key-generation numbers, not only candidate-loop screening ratios.

## Python API

Install the Python package from the repo root:

```bash
python3 -m pip install -e ./src/python
```

Use the production prefilter:

```python
from geodesic_prime_prefilter import CDLPrimeGeodesicPrefilter

p_prefilter = CDLPrimeGeodesicPrefilter(bit_length=1024, namespace="rsa-demo:p")
q_prefilter = CDLPrimeGeodesicPrefilter(bit_length=1024, namespace="rsa-demo:q")

p = p_prefilter.generate_prime(public_exponent=65537)
q = q_prefilter.generate_prime(public_exponent=65537, excluded_values={p})
```

For a one-line path:

```python
from geodesic_prime_prefilter import generate_prime

p = generate_prime(bit_length=1024, namespace="rsa-demo:p")
```

## Repository Layout

- `spec/`: Language-neutral contract and deterministic golden vectors
- `src/python/`: Python package for `v0.1.0`
- `tests/python/`: Python unit and vector tests
- `benchmarks/python/`: Candidate-loop and end-to-end RSA benchmarks
- `docs/`: Architecture notes, benchmark summary, and manual validation steps

## Validation

This repo uses manual validation only. Run the exact command sequence in [docs/manual_validation.md](docs/manual_validation.md).
