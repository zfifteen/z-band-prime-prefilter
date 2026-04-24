"""Static forbidden-dependency gate for the pure PGS generator path."""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "gmpy2",
        "sympy",
        "z_band_prime_composite_field",
        "z_band_prime_predictor",
        "benchmarks.python.predictor",
    }
)
FORBIDDEN_IMPORTED_NAMES = frozenset(
    {
        "divisor_counts_segment",
        "gwr_next_prime",
        "next_prime_after",
        "gwr_dni_recursive_walk",
    }
)
FORBIDDEN_CALL_NAMES = frozenset(
    {
        "is_prime",
        "isprime",
        "nextprime",
        "prime",
        "primerange",
        "prevprime",
        "divisor_counts_segment",
        "gwr_next_prime",
        "next_prime_after",
        "scan_to_first_prime",
        "find_next_prime",
        "miller_rabin",
        "is_probable_prime",
        "sieve_primes",
    }
)
FORBIDDEN_CALL_SUBSTRINGS = (
    "next_prime",
    "find_next_prime",
    "scan_to_first_prime",
    "miller_rabin",
)


def _attribute_name(node: ast.AST) -> str | None:
    """Return a dotted attribute/call name when it is statically visible."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_name(node.value)
        if parent is None:
            return node.attr
        return f"{parent}.{node.attr}"
    return None


def forbidden_dependency_violations(path: Path) -> list[str]:
    """Return forbidden import or call violations for one Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS or alias.name in FORBIDDEN_IMPORTED_NAMES:
                    violations.append(f"{path}: forbidden import {alias.name}")

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS or module in FORBIDDEN_IMPORTED_NAMES:
                violations.append(f"{path}: forbidden import from {module}")
            for alias in node.names:
                if alias.name in FORBIDDEN_IMPORTED_NAMES or alias.name in FORBIDDEN_CALL_NAMES:
                    violations.append(f"{path}: forbidden imported name {alias.name}")

        if isinstance(node, ast.Call):
            call_name = _attribute_name(node.func)
            if call_name is None:
                continue
            leaf = call_name.rsplit(".", 1)[-1]
            if leaf in FORBIDDEN_CALL_NAMES:
                violations.append(f"{path}: forbidden call {call_name}")
                continue
            if any(part in leaf for part in FORBIDDEN_CALL_SUBSTRINGS):
                violations.append(f"{path}: forbidden call {call_name}")

    return violations


def assert_no_forbidden_dependencies(paths: list[Path]) -> None:
    """Raise AssertionError if any source file contains forbidden dependencies."""
    violations: list[str] = []
    for path in paths:
        violations.extend(forbidden_dependency_violations(path))
    if violations:
        raise AssertionError("\n".join(violations))


__all__ = [
    "FORBIDDEN_CALL_NAMES",
    "FORBIDDEN_IMPORT_ROOTS",
    "FORBIDDEN_IMPORTED_NAMES",
    "assert_no_forbidden_dependencies",
    "forbidden_dependency_violations",
]
