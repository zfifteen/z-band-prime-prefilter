# Proof Bridge for the No-Early-Spoiler Condition

This note records the analytic bridge used for the universal proof of the
`Gap Winner Rule` (`GWR`).

The explicit constants have now been evaluated against the committed finite
base. Under BHP's $\theta = 0.525$ and the divisor-function constants recorded
below, the bridge threshold lands below the exact finite scan through
$p < 20{,}000{,}001$. So the universal `GWR` bridge is closed under the stated
assumptions.

Its job is:

- restate the exact no-early-spoiler target in one normalized quantity,
- derive a fully non-empirical large-$p$ bridge from gap geometry and divisor
  growth bounds,
- record the explicit certificate that the finite verification obligation is
  already covered by the committed exact base.

## 1. Reduction Already Established

The ordered dominance theorem is already proved in
[`../../findings/lexicographic_raw_z_dominance_theorem.md`](../../findings/lexicographic_raw_z_dominance_theorem.md):

for composite integers $a < b$, if $d(a) \le d(b)$, then

$$L(a) > L(b).$$

where

$$L(n) = \left(1 - \frac{d(n)}{2}\right)\ln(n).$$

So inside a prime gap, once the leftmost minimum-divisor carrier $w$ appears,
every later candidate is already eliminated.

The earlier side is the bridge target:

for every earlier interior candidate $k < w$ with

$$\delta = d(k) - d_{\min} \ge 1.$$

prove

$$L(k) < L(w).$$

Equivalently,

$$\frac{\ln w}{\ln k} < 1 + \frac{\delta}{d_{\min} - 2}.$$

## 2. Normalized Bridge Load

Define the dimensionless bridge quantity

$$B(k,w) = \frac{\frac{\ln w}{\ln k} - 1}{\frac{\delta}{d_{\min} - 2}}.$$

$$B(k,w) < 1.$$

This is equivalent to $L(k) < L(w)$.

This is the normalized quantity measured directly by
[`asymptotic_bridge_load_scan.py`](./asymptotic_bridge_load_scan.py).

## 3. Deterministic Upper Bound On The Numerator

Let $g(p) = q - p$ denote the prime gap.

For any earlier candidate $k$ and winner $w$ in the gap interior,

$$w - k \le g(p).$$

For $x > -1$, use

$$\ln(1 + x) \le x.$$

one has

$$\ln\frac{w}{k} = \ln\left(1 + \frac{w - k}{k}\right) \le \frac{w - k}{k} \le \frac{g(p)}{p+1} < \frac{g(p)}{p}.$$

Because $\ln k > \ln p$, it follows that

$$\frac{\ln w}{\ln k} - 1 = \frac{\ln(w/k)}{\ln k} < \frac{g(p)}{p \ln p}.$$

So the bridge numerator is controlled purely by gap geometry.

## 4. Deterministic Lower Bound On The Denominator

For every earlier candidate,

$$\delta \ge 1.$$

So

$$\frac{\delta}{d_{\min} - 2} \ge \frac{1}{d_{\min} - 2}.$$

Now use any explicit maximal-order upper bound for the divisor function, for
example a Nicolas-Robin style majoration of the form

$$d(n) \le \exp\left(c \frac{\ln n}{\ln\ln n}\right)$$

for all sufficiently large $n$, with an effective absolute constant $c > 0$.

Since $w$ lies in the gap interior near $p$, this gives

$$d_{\min} - 2 \le \exp\left(c \frac{\ln p}{\ln\ln p}\right)$$

for all sufficiently large $p$, hence

$$\frac{\delta}{d_{\min} - 2} \ge \exp\left(-c \frac{\ln p}{\ln\ln p}\right).$$

So the bridge denominator is bounded below by a subpolynomial term.

## 5. Universal Large-$p$ Bridge

Combine the numerator and denominator bounds:

$$B(k,w) < \frac{g(p)}{p \ln p} \cdot \exp\left(c \frac{\ln p}{\ln\ln p}\right).$$

Now assume any proved prime-gap upper bound of the form

$$g(p) \le p^\theta$$

for all sufficiently large $p$, with some fixed $\theta < 1$.

Then

$$B(k,w) < p^{\theta - 1} (\ln p)^{-1} \exp\left(c \frac{\ln p}{\ln\ln p}\right) = p^{\theta - 1 + o(1)}.$$

Because $\theta < 1$, the exponent $\theta - 1 + o(1)$ is eventually
negative. Therefore

$$B(k,w) \to 0.$$

as $p \to \infty$.

So there exists an effective threshold $N_{bridge}$ such that for all
prime gaps with left endpoint $p \ge N_{bridge}$,

$$B(k,w) < 1.$$

for every earlier candidate $k$.

This is the universal large-$p$ lemma.

## 6. Explicit Certificate

The explicit certificate artifact is
[`../../../output/gwr_proof/proof_bridge_certificate_2e7.json`](../../../output/gwr_proof/proof_bridge_certificate_2e7.json).

It evaluates the bridge bound

$$B(k,w) < A p^{\theta-1}(\ln p)^{-1}\exp(c\ln p/\ln\ln p).$$

Against BHP's $\theta = 0.525$, the evaluated thresholds are:

| Constants | Raw threshold where bridge is below `1` | Relation to finite base |
|---|---:|---|
| $A=1$, $c=\ln(2)e^\gamma$ | `102` | inside $p < 20{,}000{,}001$ |
| $A=1$, $c=1.5379$ | `3,544` | inside $p < 20{,}000{,}001$ |
| $A=10$, $c=\ln(2)e^\gamma$ | `220,725` | inside $p < 20{,}000{,}001$ |
| $A=10$, $c=1.5379$ | `727,330,778` | outside current finite base |

The exact finite bridge-load base through $p < 20{,}000{,}001$ records:

- `3,349,874` earlier candidates,
- `0` bridge failures,
- maximum realized bridge load `0.05664166714743768`.

Therefore the headline $A=1$ bridge closes under both recorded divisor
constants. The $A=10$ robustness variant closes under Robin's
$c=\ln(2)e^\gamma$ constant, but not under the conservative $c=1.5379$ constant
with the current finite base.

## 7. Current Role Of The Exact Artifacts

The exact artifacts no longer serve only as evidence.

They serve two proof roles:

- they certify the finite base already covered exactly in the repo;
- they provide the base case below the explicit analytic threshold.

The bridge proof supplies the tail above the threshold. Since the threshold is
below the finite base for the headline $A=1$ constants, the two regimes overlap.

That overlap is the closure: there is no unverified interval between the exact
finite computation and the large-$p$ bridge under the stated assumptions.
