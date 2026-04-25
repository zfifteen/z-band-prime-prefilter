# Explicit-A Bridge One-Shot Audit

## Result

The analytic bridge is not closed by the currently public literature.

No publicly verifiable unconditional theorem was found with

$$g(p) \le A p^{0.525}$$

for every prime $p \ge 5 \cdot 10^9$ and

$$A < 14.246224287129907.$$

No publicly verifiable theorem was found that closes the relaxed handoff at

$$P_0 = 5{,}571{,}362{,}243{,}795$$

with

$$A < 52.627783539395274.$$

The missing ingredient remains a numerical effective threshold for a
Baker-Harman-Pintz or Harman-sieve theorem in the $\theta = 0.525$ regime.

## Bridge Contract Checked

The comparison bridge in
[`./proof_bridge_universal_lemma.md`](./proof_bridge_universal_lemma.md) uses

$$E_{\theta,c,A}(p) = A p^{\theta - 1}(\ln p)^{-1}\exp\left(c\frac{\ln p}{\ln\ln p}\right),$$

with $\theta = 0.525$ and conservative Nicolas-Robin constant $c = 1.5379$.
Because

$$0.525 < 1 - \frac{1.5379}{4},$$

this envelope is decreasing for $p > e^e$. The tail therefore reduces to the
one-point budget

$$A < A_{\max}(P_0;\theta,c) = P_0^{1-\theta}\ln P_0\exp\left(-c\frac{\ln P_0}{\ln\ln P_0}\right).$$

The deterministic checker
[`./explicit_a_bridge_envelope_check.py`](./explicit_a_bridge_envelope_check.py)
returns:

| Handoff | $A_{\max}$ | $E(P_0)$ when $A = 1$ |
|---|---:|---:|
| $5 \cdot 10^9$ | $14.246224287129907$ | $0.07019403737054764$ |
| $5{,}571{,}362{,}243{,}795$ | $52.62778353939529$ | $0.019001370241090162$ |

Thus $A = 1$ would close either handoff with a wide numerical margin. The
obstruction is not the leading constant. The obstruction is the absence of a
public effective threshold at or below the retained handoff.

## Source Audit

### Baker-Harman-Pintz

Baker, Harman, and Pintz prove that an interval of length $x^{0.525}$ contains
a prime for large $x$.

Source:
[Cambridge Core, Proceedings of the London Mathematical Society](https://www.cambridge.org/core/journals/proceedings-of-the-london-mathematical-society/article/abs/difference-between-consecutive-primes-ii/2EF13261B3B25458A25F41ED74AA2FC2)

This is the right exponent and leading scale for the bridge. The public
statement does not provide a numerical threshold $x_0$. Without that threshold,
the theorem cannot be imported into the bridge at $5 \cdot 10^9$.

### Runbo Li

Li reports lower and upper bounds for primes in $[x - x^\theta,x]$ for
$0.52 \le \theta \le 0.525$, including the statement that
$[x - x^{0.52},x]$ contains a prime for sufficiently large $x$.

Source:
[arXiv:2308.04458](https://arxiv.org/abs/2308.04458)

This improves the exponent regime, but the public abstract-level theorem is
still asymptotic at the threshold level needed here. The arXiv record includes
ancillary numerical programs, but the public theorem statement does not certify
an $x_0 \le 5 \cdot 10^9$ or an $x_0$ below the relaxed Dusart handoff.

### Visser

Visser supplies effective short-interval statements of the form
$[x,x+x^{1-1/n}]$, including explicit thresholds for several exponent
families.

Source:
[arXiv:2508.18786](https://arxiv.org/abs/2508.18786)

These results are effective, but their exponents are too large for the
$\theta = 0.525$ bridge budget. A bound of the form $g(p) \le p^\alpha$ with
$\alpha > 0.525$ cannot be converted into a fixed $A p^{0.525}$ tail bound
for all larger $p$.

### MathOverflow Status Check

The public MathOverflow discussion reports that no explicit value of the
Baker-Harman-Pintz threshold has been computed publicly.

Source:
[MathOverflow question 503146](https://mathoverflow.net/questions/503146/has-an-explicit-value-of-x-0-been-computed-in-the-baker-harman-pintz-theor)

This is not a theorem source, but it matches the literature audit: the BHP
threshold is effective in principle and unspecified in public numerical form.

## Why Existing Explicit Bounds Do Not Close The Tail

The Dusart bound used in the bridge note gives a bounded unconditional bridge
window. It does not supply a fixed-exponent tail of the required form. Written
against $p^{0.525}$, its effective coefficient grows like

$$\frac{p^{0.475}}{25(\ln p)^2},$$

which eventually exceeds every fixed bridge budget.

Explicit short-interval theorems with exponent $\alpha > 0.525$ have the same
tail obstruction: $p^\alpha = p^{\alpha-0.525}p^{0.525}$, and the multiplier
$p^{\alpha-0.525}$ is unbounded.

## One-Shot Conclusion

The requested bridge-closing theorem was not produced or extracted.

The correct repo status remains:

1. the current GWR proof surface stays closed by the existing
   local-dominator, local-admissibility, residual-closure, and audit route;
2. the normalized bridge remains comparison material;
3. the open analytic task is unchanged but sharper: compute a public effective
   threshold for a $\theta = 0.525$ Harman-sieve theorem, ideally BHP with
   $A = 1$, and show that the threshold lies no later than one retained
   handoff.

The bridge file should not be marked closed analytically until such an
explicit theorem is available.
