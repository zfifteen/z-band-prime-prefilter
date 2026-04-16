# Prime-Gap Exclusion Consequences of GWR

This note records the cleanest way to think about the intuition that the Gap
Winner Rule says something about what primes cannot do.

The safest version of that intuition is local, not global:

- GWR does not by itself give a new formula for $\pi(x)$ or a new asymptotic
  law for prime gaps.
- What it does give is a family of exclusion constraints on the composite
  interiors that consecutive primes are allowed to enclose.

That is already a genuine prime-distribution statement, because prime gaps are
defined by consecutive primes.

## Setting

Let $(p, q)$ be a prime gap with interior integers

$$
p + 1,\; p + 2,\; \ldots,\; q - 1.
$$

Write the winner as

$$
m = p + r
$$

with divisor count

$$
\delta = d(m).
$$

Under GWR, the winner is the leftmost interior integer with minimal divisor
count.

## Exact Left-Prefix Exclusion Corollary

If GWR holds on the gap $(p, q)$ and the winner is $m = p + r$ with
$\delta = d(m)$, then every earlier interior integer satisfies

$$
d(p + i) > \delta \qquad \text{for all } 1 \le i < r.
$$

In words:

Before the winner appears, the gap interior cannot contain any earlier integer
whose divisor count is as small as, or smaller than, the winner's divisor
count.

### Proof

If some earlier interior integer $p + i$ had

$$
d(p + i) < \delta,
$$

then it would beat $m$ under the GWR rule because it has smaller divisor count.

If some earlier interior integer $p + i$ had

$$
d(p + i) = \delta,
$$

then it would also beat $m$ under GWR because ties go to the leftmost interior
integer.

So no earlier interior integer can satisfy

$$
d(p + i) \le \delta.
$$

That gives the stated exclusion condition.

## Exact Right-Suffix Exclusion Corollary

If GWR holds on the gap $(p, q)$ and the winner is $m = p + r$ with
$\delta = d(m)$, then every later interior integer satisfies

$$
d(p + i) \ge \delta \qquad \text{for all } r < i < q - p.
$$

In words:

After the winner appears, the rest of the gap cannot contain any later interior
integer with strictly smaller divisor count.

### Proof

If some later interior integer $p + i$ had

$$
d(p + i) < \delta,
$$

then $m$ would not have minimal divisor count on the gap interior, so it could
not be the GWR winner.

That gives the stated suffix condition.

## Combined Divisor-Profile Form

The left-prefix and right-suffix statements combine into one clean picture.

If the winner is $m = p + r$ with $\delta = d(m)$, then the divisor counts
across the gap interior must have the form

$$
>\delta,\ >\delta,\ \ldots,\ >\delta,\ \delta,\ \ge \delta,\ \ge \delta,\ \ldots,\ \ge \delta.
$$

So the winner is the first place in the gap where the divisor-count profile
reaches its minimum.

## What This Means

This is the cleanest way to express the idea that GWR tells us what primes
cannot do.

If consecutive primes $p < q$ bound a gap whose winner is $m = p + r$, then
those primes were not free to enclose an arbitrary interior divisor profile.
They were forced to avoid every interior integer with divisor count at most
$\delta$ before offset $r$.

So GWR does not merely identify the winner. It also identifies a forbidden
prefix and a constrained suffix:

$$
p + 1,\; p + 2,\; \ldots,\; p + r - 1
$$

must avoid the divisor classes

$$
d(n) \le \delta.
$$

Meanwhile the suffix

$$
p + r + 1,\; p + r + 2,\; \ldots,\; q - 1
$$

must avoid the divisor classes

$$
d(n) < \delta.
$$

That is a genuine exclusion statement about prime-gap interiors.

## Immediate Concrete Cases

If the winner has $d(m) = 3$, then there can be no earlier interior integer
with divisor count $3$. In particular, there can be no earlier prime square.

If the winner has $d(m) = 4$, then there can be no earlier interior integer
with divisor count $3$ or $4$. In particular, there can be no earlier prime
square, no earlier semiprime of the form $ab$ with distinct primes $a$ and
$b$, and no earlier prime cube. There can also be no later interior integer
with divisor count $3$ before the next prime closes the gap.

More generally, a later winner with small divisor count forces a longer prefix
that is free of all equally simple or simpler divisor classes.

## Why This Touches Prime Distribution

The gap interior is not chosen independently of the primes. It is created by
the consecutive primes that bound it.

So once GWR is assumed, any observed winner at offset $r$ with divisor class
$\delta$ can be re-read as a statement about what the primes $p$ and $q$ failed
to leave behind before the winner, and what they did not allow to appear after
the winner before the gap closed.

That is why the intuition points toward prime distribution rather than only
toward score geometry.

The exact statement is still local:

- a winner at offset $r$ forces a forbidden prefix of length $r - 1$,
- it also forces a suffix with no strictly smaller divisor class,
- the forbidden prefix is defined by divisor-count exclusion,
- therefore consecutive primes cannot bound arbitrary interior composite
  patterns.

## A Plausible Heuristic Consequence

This exact exclusion corollary suggests a mechanism for the observed left-edge
dominance.

Later winners are combinatorially expensive. To place a winner at offset $r$,
the gap must avoid all divisor classes $d(n) \le \delta$ throughout the entire
prefix of length $r - 1$, hit such a class at the winner itself, and then avoid
all divisor classes $d(n) < \delta$ until the next prime closes the gap.

Since low-divisor classes such as $d(n) = 3$ and $d(n) = 4$ recur regularly,
that avoidance condition becomes more restrictive as $r$ grows.

This is not itself a separate global law for winner offsets. But it gives a
clean mechanism for why

- left-edge winners are common,
- edge-distance $2$ is enriched,
- and $d(n) = 4$ winners dominate when no earlier $d(n) = 3$ or $d(n) = 4$
  carrier is available.

## Claim Ladder

It helps to keep the statuses separate.

### Exact consequence of GWR

If GWR holds on a gap, then the prefix before the winner is free of divisor
classes at most as small as the winner's divisor count, and the suffix after
the winner is free of strictly smaller divisor classes.

### Evidence-backed observation on the tested surface

The tested surfaces show strong left-edge concentration and strong enrichment in
low-divisor winner classes, especially $d(n) = 4$.

### Broader distribution reading

Because `GWR` is proved on the repo's current proof surface, one broader
distribution reading is that prime gaps may be governed by a forbidden-prefix
principle: later winners require increasingly restrictive exclusion of low-
divisor composites near the left side of the gap.

## Safe Summary

The safest way to state the intuition is:

The Gap Winner Rule does not give a global prime-counting law by itself, but it
does impose exact local exclusion constraints on prime-gap interiors. In that
sense, it says not only which interior composite wins, but also which earlier
equally simple or simpler composites could not occur before it, and which
strictly simpler composites could not occur after it before the gap closed.
