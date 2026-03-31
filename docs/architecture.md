# Architecture

The repository is a single monorepo with one shared contract and separate implementation subtrees per language.

## Current Structure

- `spec/` holds the invariant algorithm contract and the deterministic golden vectors.
- `src/python/` is the only implementation subtree in `v0.1.0`.
- `tests/python/` and `benchmarks/python/` validate only the Python path.

## Future Ports

Java and Apple-Silicon-only C99/GMP/MPFR will land as sibling subtrees:

- `src/java/`
- `src/c/`
- `tests/java/`
- `tests/c/`
- `benchmarks/java/`
- `benchmarks/c/`

The Python tree will not move when those ports arrive.

## Source of Truth

- The contract in `spec/contract.md` defines the deterministic behavior each language must match.
- The JSON files in `spec/vectors/` are the cross-language parity surface.
- Python is the initial normative executable implementation.
- C becomes the reference implementation only after it matches the same vectors and manual validation results.

## Artifact Separation

- Generated benchmark outputs go to `benchmarks/output/<language>/`.
- Those outputs are gitignored.
- Only curated summaries and deterministic golden vectors are committed.
