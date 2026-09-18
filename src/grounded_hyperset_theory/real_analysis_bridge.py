"""Reachability of classical calculus: Dedekind cuts, Cauchy sequences, and surreals grounded in hyperset ordinals."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Sequence

from .hyperset import EmptyHyperset, Hyperset, pair, von_neumann_ordinal


@dataclass(frozen=True)
class GroundedInteger:
    """An exact signed integer grounded as a Kuratowski pair of von Neumann ordinals."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise TypeError(f"GroundedInteger requires exact int, got {type(self.value).__name__}")

    def to_hyperset(self) -> Hyperset:
        """Ground into Kuratowski pair (a, b) where value = a - b."""
        if self.value >= 0:
            return pair(von_neumann_ordinal(self.value), von_neumann_ordinal(0))
        return pair(von_neumann_ordinal(0), von_neumann_ordinal(-self.value))

    def __add__(self, other: GroundedInteger | int) -> GroundedInteger:
        v = other.value if isinstance(other, GroundedInteger) else other
        return GroundedInteger(self.value + v)

    def __sub__(self, other: GroundedInteger | int) -> GroundedInteger:
        v = other.value if isinstance(other, GroundedInteger) else other
        return GroundedInteger(self.value - v)

    def __mul__(self, other: GroundedInteger | int) -> GroundedInteger:
        v = other.value if isinstance(other, GroundedInteger) else other
        return GroundedInteger(self.value * v)

    def __neg__(self) -> GroundedInteger:
        return GroundedInteger(-self.value)

    def __lt__(self, other: GroundedInteger | int) -> bool:
        v = other.value if isinstance(other, GroundedInteger) else other
        return self.value < v

    def __le__(self, other: GroundedInteger | int) -> bool:
        v = other.value if isinstance(other, GroundedInteger) else other
        return self.value <= v

    def __gt__(self, other: GroundedInteger | int) -> bool:
        v = other.value if isinstance(other, GroundedInteger) else other
        return self.value > v

    def __ge__(self, other: GroundedInteger | int) -> bool:
        v = other.value if isinstance(other, GroundedInteger) else other
        return self.value >= v

    def __int__(self) -> int:
        return self.value

    def __repr__(self) -> str:
        return f"ℤ({self.value})"


@dataclass(frozen=True)
class GroundedRational:
    """An exact rational number p/q grounded as a Kuratowski pair of GroundedIntegers."""

    numerator: int
    denominator: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.numerator, int) or isinstance(self.numerator, bool):
            raise TypeError("Numerator must be an exact integer")
        if not isinstance(self.denominator, int) or isinstance(self.denominator, bool):
            raise TypeError("Denominator must be an exact integer")
        if self.denominator == 0:
            raise ZeroDivisionError("Rational denominator cannot be zero")

        # Canonicalize sign and reduce by gcd
        num = self.numerator
        den = self.denominator
        if den < 0:
            num = -num
            den = -den
        g = math.gcd(abs(num), den)
        object.__setattr__(self, "numerator", num // g)
        object.__setattr__(self, "denominator", den // g)

    def to_hyperset(self) -> Hyperset:
        """Ground this rational as a Kuratowski pair of grounded numerator and denominator."""
        p = GroundedInteger(self.numerator).to_hyperset()
        q = GroundedInteger(self.denominator).to_hyperset()
        return pair(p, q)

    def to_float(self) -> float:
        return self.numerator / self.denominator

    def __float__(self) -> float:
        return self.to_float()

    def __add__(self, other: GroundedRational | int) -> GroundedRational:
        if isinstance(other, int):
            return GroundedRational(self.numerator + other * self.denominator, self.denominator)
        return GroundedRational(
            self.numerator * other.denominator + other.numerator * self.denominator,
            self.denominator * other.denominator,
        )

    def __sub__(self, other: GroundedRational | int) -> GroundedRational:
        if isinstance(other, int):
            return GroundedRational(self.numerator - other * self.denominator, self.denominator)
        return GroundedRational(
            self.numerator * other.denominator - other.numerator * self.denominator,
            self.denominator * other.denominator,
        )

    def __mul__(self, other: GroundedRational | int) -> GroundedRational:
        if isinstance(other, int):
            return GroundedRational(self.numerator * other, self.denominator)
        return GroundedRational(
            self.numerator * other.numerator,
            self.denominator * other.denominator,
        )

    def __truediv__(self, other: GroundedRational | int) -> GroundedRational:
        if isinstance(other, int):
            return GroundedRational(self.numerator, self.denominator * other)
        if other.numerator == 0:
            raise ZeroDivisionError("Division by zero rational")
        return GroundedRational(
            self.numerator * other.denominator,
            self.denominator * other.numerator,
        )

    def __neg__(self) -> GroundedRational:
        return GroundedRational(-self.numerator, self.denominator)

    def __lt__(self, other: GroundedRational | int) -> bool:
        if isinstance(other, int):
            return self.numerator < other * self.denominator
        return self.numerator * other.denominator < other.numerator * self.denominator

    def __le__(self, other: GroundedRational | int) -> bool:
        if isinstance(other, int):
            return self.numerator <= other * self.denominator
        return self.numerator * other.denominator <= other.numerator * self.denominator

    def __gt__(self, other: GroundedRational | int) -> bool:
        if isinstance(other, int):
            return self.numerator > other * self.denominator
        return self.numerator * other.denominator > other.numerator * self.denominator

    def __ge__(self, other: GroundedRational | int) -> bool:
        if isinstance(other, int):
            return self.numerator >= other * self.denominator
        return self.numerator * other.denominator >= other.numerator * self.denominator

    def __repr__(self) -> str:
        if self.denominator == 1:
            return f"ℚ({self.numerator})"
        return f"ℚ({self.numerator}/{self.denominator})"


class DedekindCut:
    """A real number represented as a Dedekind lower cut L = {q in Q : q < x}."""

    def __init__(self, predicate: Callable[[GroundedRational], bool], name: str = "real") -> None:
        self.predicate = predicate
        self.name = name

    def contains(self, q: GroundedRational | int) -> bool:
        """Return True if rational q is in the lower cut L."""
        r = q if isinstance(q, GroundedRational) else GroundedRational(q)
        return self.predicate(r)

    def __contains__(self, q: Any) -> bool:
        if isinstance(q, (GroundedRational, int)):
            return self.contains(q)
        return False

    @classmethod
    def from_rational(cls, r: GroundedRational | int) -> DedekindCut:
        """The Dedekind cut representing a rational number r: L = {q in Q : q < r}."""
        target = r if isinstance(r, GroundedRational) else GroundedRational(r)
        return cls(predicate=lambda q: q < target, name=f"cut_{target}")

    @classmethod
    def sqrt_two(cls) -> DedekindCut:
        """The Dedekind cut for sqrt(2): L = {q in Q : q <= 0 or q^2 < 2}."""
        two = GroundedRational(2)
        zero = GroundedRational(0)
        return cls(
            predicate=lambda q: q <= zero or (q * q < two),
            name="√2",
        )

    @classmethod
    def golden_ratio(cls) -> DedekindCut:
        """The Dedekind cut for the golden ratio phi = (1 + sqrt(5))/2 (~1.6180339...)."""
        zero = GroundedRational(0)
        return cls(
            predicate=lambda q: q <= zero or (q * q - q - GroundedRational(1) < zero),
            name="φ",
        )

    def binary_search_interval(
        self,
        low: GroundedRational,
        high: GroundedRational,
        iterations: int = 25,
    ) -> tuple[GroundedRational, GroundedRational]:
        """Narrow the bounding interval [low, high] around this real cut via rational bisection."""
        lo = low
        hi = high
        half = GroundedRational(1, 2)
        for _ in range(iterations):
            mid = (lo + hi) * half
            if self.contains(mid):
                lo = mid
            else:
                hi = mid
        return lo, hi

    def downward_closure_violation(
        self,
        search: Sequence[GroundedRational] | None = None,
    ) -> tuple[GroundedRational, GroundedRational] | None:
        """A pair ``(low, high)`` with ``low < high``, ``high`` in the cut and ``low`` not.

        A Dedekind lower cut is downward closed: if ``high`` is in ``L`` and
        ``low < high`` then ``low`` is in ``L``. Such a pair therefore proves the
        predicate is not a lower cut and represents no real number.

        As with every check of a black-box predicate, the two answers differ in
        kind. A returned pair is a **proof** of failure. ``None`` means no
        violation was found among ``search``, which is not a proof of anything:
        the predicate is an arbitrary callable and the search is finite.

        This is deliberately not called from ``__init__``. Wiring a search that
        cannot certify into a constructor would make construction look like
        certification, which is the mistake this file is being cleaned of.
        """
        if search is None:
            search = [
                GroundedRational(n, d)
                for d in (1, 2, 3, 4)
                for n in range(-4 * d, 4 * d + 1)
            ]
        members = [q for q in search if self.contains(q)]
        outside = [q for q in search if not self.contains(q)]
        for high in members:
            for low in outside:
                if low < high:
                    return (low, high)
        return None

    def approximate(self, iterations: int = 25, bracket_limit: int = 64) -> float:
        """Floating-point approximation of this cut, by bracketing then bisection.

        Brackets the cut between a rational inside ``L`` and one outside it, then
        bisects. Both searches are bounded: an unbounded search does not
        terminate on a predicate that is constantly True or constantly False, and
        neither of those is a real number.

        Raises:
            ValueError: if no bracket is found within ``bracket_limit`` doublings
                or steps. The empty cut and the full cut both land here. They
                previously ran forever -- the first loop doubled ``high`` without
                end, the second stepped ``low`` down by 2 without end.
        """
        low = GroundedRational(0)
        high = GroundedRational(1)

        steps = 0
        while self.contains(high):
            low = high
            high = high * 2
            steps += 1
            if steps > bracket_limit:
                raise ValueError(
                    f"no rational outside the cut found below {high.to_float():g} "
                    f"after {bracket_limit} doublings; a Dedekind lower cut must "
                    f"have a non-empty complement, so this predicate is not one "
                    f"(the constantly-True predicate behaves this way)"
                )

        steps = 0
        while not self.contains(low):
            high = low
            low = low - 2
            steps += 1
            if steps > bracket_limit:
                raise ValueError(
                    f"no rational inside the cut found above {low.to_float():g} "
                    f"after {bracket_limit} steps; a Dedekind lower cut must be "
                    f"non-empty, so this predicate is not one (the "
                    f"constantly-False predicate behaves this way)"
                )

        lo, hi = self.binary_search_interval(low, high, iterations=iterations)
        return (lo.to_float() + hi.to_float()) / 2.0

    def to_hyperset(self, sample_rationals: Sequence[GroundedRational]) -> Hyperset:
        """Ground a sample of members of this Dedekind lower cut into a Hyperset."""
        members = [q.to_hyperset() for q in sample_rationals if self.contains(q)]
        return Hyperset.from_elements(*members)

    def __repr__(self) -> str:
        return f"DedekindCut({self.name})"


@dataclass(frozen=True)
class CauchySequence:
    """A Cauchy sequence of grounded rationals defining a real number."""

    term_fn: Callable[[int], GroundedRational]
    name: str = "cauchy_seq"

    def term(self, n: int) -> GroundedRational:
        """Evaluate the nth term of the sequence (0-indexed)."""
        if n < 0:
            raise ValueError("Index must be non-negative")
        return self.term_fn(n)

    def __getitem__(self, n: int) -> GroundedRational:
        return self.term(n)

    def cauchy_violation(
        self,
        check_terms: int = 15,
        epsilon: float = 0.05,
        reach: int = 4,
    ) -> tuple[int, int, float] | None:
        """A triple ``(m, n, |a_m - a_n|)`` with the gap at least ``epsilon``, or None.

        Indices are drawn from two places: the contiguous tail of the first
        ``check_terms`` terms, and ``reach`` further indices spaced
        geometrically -- ``check_terms``, ``2 * check_terms``, ``4 *
        check_terms``, and so on. The geometric part is what makes the check
        worth running. A contiguous window alone is quiet on any sequence that
        happens to be quiet there, including sequences that diverge:
        ``a_n = ln(n)/100`` moves by less than 0.03 across the first fifteen
        terms and grows without bound afterwards.

        A returned triple is a **proof** that the sequence is not Cauchy at
        ``epsilon``. ``None`` is not a proof of the converse -- see
        ``is_cauchy``.
        """
        if check_terms < 2:
            raise ValueError(f"check_terms must be at least 2, got {check_terms}")
        if epsilon <= 0:
            raise ValueError(f"epsilon must be positive, got {epsilon}")
        if reach < 0:
            raise ValueError(f"reach must be non-negative, got {reach}")

        indices = list(range(max(1, check_terms // 2), check_terms))
        indices += [check_terms * (2 ** i) for i in range(reach)]

        for i, m in enumerate(indices):
            for n in indices[i + 1:]:
                diff = abs((self.term(m) - self.term(n)).to_float())
                if diff >= epsilon:
                    return (m, n, diff)
        return None

    def is_cauchy(self, check_terms: int = 15, epsilon: float = 0.05) -> bool:
        """Whether ``cauchy_violation`` finds no pair of terms at least ``epsilon`` apart.

        The two answers are not worth the same.

        **False is conclusive.** Some pair ``(m, n)`` has ``|a_m - a_n| >=
        epsilon``, which is incompatible with the Cauchy criterion at that
        ``epsilon``. ``cauchy_violation`` returns the pair.

        **True is not a proof.** The criterion quantifies over all ``m, n``
        past some index, and this samples finitely many. Raising ``check_terms``
        makes a pass mean more; no finite value makes it mean convergence. A
        sequence that is flat over everything sampled and then moves will pass,
        and that is not a hypothetical: before the sampling reached past the
        window, a sequence identically zero until n = 15 and equal to ``n``
        afterwards was certified Cauchy.

        Use ``cauchy_violation`` when the witness matters, which is whenever the
        answer is going to be recorded as evidence.
        """
        return self.cauchy_violation(check_terms=check_terms, epsilon=epsilon) is None

    def limit_approx(self, n: int = 30) -> float:
        """Evaluate floating point approximation at step n."""
        return self.term(n).to_float()

    def to_hyperset(self, count: int = 5) -> Hyperset:
        """Ground initial terms into an ordered hyperset."""
        terms = [self.term(i).to_hyperset() for i in range(count)]
        return Hyperset.from_elements(*terms)

    @classmethod
    def euler_e(cls) -> CauchySequence:
        """Cauchy sequence for Euler's number e = sum_{k=0}^n 1/k!."""
        def calc(n: int) -> GroundedRational:
            total = GroundedRational(1)
            fact = 1
            for k in range(1, n + 1):
                fact *= k
                total = total + GroundedRational(1, fact)
            return total
        return cls(term_fn=calc, name="e")

    @classmethod
    def pi_leibniz(cls) -> CauchySequence:
        """Cauchy sequence for pi via Leibniz formula: 4 * sum_{k=0}^n (-1)^k / (2k+1)."""
        def calc(n: int) -> GroundedRational:
            total = GroundedRational(0)
            for k in range(n + 1):
                sign = 1 if k % 2 == 0 else -1
                total = total + GroundedRational(sign * 4, 2 * k + 1)
            return total
        return cls(term_fn=calc, name="π")

    @classmethod
    def geometric(cls, ratio: GroundedRational) -> CauchySequence:
        """Cauchy sequence for geometric series sum_{k=0}^n r^k for |r| < 1."""
        if abs(ratio.to_float()) >= 1.0:
            raise ValueError("Geometric series requires |r| < 1 for Cauchy convergence")
        def calc(n: int) -> GroundedRational:
            total = GroundedRational(0)
            curr = GroundedRational(1)
            for _ in range(n + 1):
                total = total + curr
                curr = curr * ratio
            return total
        return cls(term_fn=calc, name=f"geom_{ratio}")


def are_equivalent_cauchy(
    seq1: CauchySequence,
    seq2: CauchySequence,
    check_n: int = 20,
    tolerance: float = 1e-3,
    tail: int = 4,
) -> bool:
    """Whether ``|a_n - b_n|`` stays below ``tolerance`` across a spread of indices.

    Equivalence of Cauchy sequences is ``lim |a_n - b_n| = 0``, a statement about
    a limit. What is checked here is ``|a_n - b_n| < tolerance`` at ``check_n``
    and at ``tail`` further indices spaced geometrically past it, and that the
    gap does not grow across them.

    **False is conclusive** at the given tolerance: some sampled index has the
    two sequences further apart than that. **True is not a proof** of equal
    limits.

    Comparing a single index, which is what this did, is much weaker than it
    looks, because two sequences can cross. ``pi_leibniz`` converges slowly
    enough that its 20th term is 3.18918, and the constant sequence at that value
    agreed with it exactly at index 20 -- so they were reported to be the same
    real number, while their limits are 0.0476 apart. Sampling past ``check_n``
    catches that particular pair; it does not make the True answer a proof.
    """
    if tail < 0:
        raise ValueError(f"tail must be non-negative, got {tail}")
    indices = [check_n] + [check_n * (2 ** i) for i in range(1, tail + 1)]
    gaps = [abs(seq1.limit_approx(n) - seq2.limit_approx(n)) for n in indices]
    if any(gap >= tolerance for gap in gaps):
        return False
    # A gap that grows along the tail is evidence against a shared limit even
    # when every sampled value is still inside the tolerance.
    return all(later <= earlier + tolerance for earlier, later in zip(gaps, gaps[1:]))


def _simplest_between(low: float | None, high: float | None) -> float:
    """The simplest number strictly between ``low`` and ``high``; None means unbounded.

    "Simplest" is Conway's: the value with the earliest birthday, which is the
    integer of least absolute value in the interval when there is one, and
    otherwise the dyadic rational with the smallest denominator.
    """
    if low is None and high is None:
        return 0.0
    if low is None:
        # Unbounded below: the simplest number under `high`.
        return float(math.ceil(high) - 1)
    if high is None:
        # Unbounded above: the simplest number over `low`.
        return float(math.floor(low) + 1)
    if low < 0.0 < high:
        return 0.0
    if high <= 0.0:
        return -_simplest_between(-high, -low)

    # 0 <= low < high. Try the least integer strictly above `low`, then dyadics
    # of increasing denominator until one lands inside.
    candidate = float(math.floor(low) + 1)
    if candidate < high:
        return candidate
    for k in range(1, 64):
        scale = float(1 << k)
        candidate = (math.floor(low * scale) + 1) / scale
        if low < candidate < high:
            return candidate
    raise ValueError(
        f"no dyadic rational found in ({low!r}, {high!r}) within 64 halvings; "
        f"the interval is narrower than double precision can resolve"
    )


@dataclass(frozen=True)
class SurrealNumber:
    """A surreal number x = { L | R } where L, R are sets of already-constructed surreals.

    In grounded hyperset theory, surreals can be well-founded (finite dyadic games)
    or non-well-founded (infinitesimals and infinite surreal numbers).
    """

    left: tuple[SurrealNumber, ...] = ()
    right: tuple[SurrealNumber, ...] = ()

    @classmethod
    def zero(cls) -> SurrealNumber:
        """Surreal 0 = { ∅ | ∅ }."""
        return cls((), ())

    @classmethod
    def one(cls) -> SurrealNumber:
        """Surreal 1 = { 0 | ∅ }."""
        return cls((cls.zero(),), ())

    @classmethod
    def minus_one(cls) -> SurrealNumber:
        """Surreal -1 = { ∅ | 0 }."""
        return cls((), (cls.zero(),))

    @classmethod
    def half(cls) -> SurrealNumber:
        """Surreal 1/2 = { 0 | 1 }."""
        return cls((cls.zero(),), (cls.one(),))

    @classmethod
    def infinitesimal(cls) -> SurrealNumber:
        """``{ 0 | 1/2, 1 }``, which is the dyadic rational 1/4 -- not an infinitesimal.

        The genuine epsilon is ``{ 0 | 1, 1/2, 1/4, 1/8, ... }`` with an
        *infinite* right set. ``left`` and ``right`` here are finite tuples and
        cannot hold one, so no value of this class is infinitesimal (see
        ``is_infinitesimal``). Truncating the right set to ``{1/2, 1}`` gives the
        simplest number in ``(0, 1/2)``, which is 1/4 -- as ``to_float`` on the
        returned value reports.

        The name is released public API and is kept, and what it returns is
        unchanged. This docstring no longer claims it is "smaller than standard
        reals", which the module's own arithmetic contradicts.
        """
        return cls((cls.zero(),), (cls.half(), cls.one()))

    def is_infinitesimal(self) -> bool:
        """Always False. No value this class can represent is infinitesimal.

        ``x`` is infinitesimal when ``0 < |x| < 1/n`` for *every* positive
        integer ``n``. ``left`` and ``right`` are finite tuples of values built
        the same way, so every representable value has a finite birthday, and a
        surreal of finite birthday is a dyadic rational ``p/2**k``; a non-zero
        one is at least ``1/2**k`` in absolute value. Reaching an infinitesimal
        needs an infinite option set.

        That is a proof about the representation rather than an unfinished
        search, which is why a constant is the honest answer here.

        It previously tested ``left == (0,) and right != ()``, which is a
        statement about the *shape* of the expression and not about its value:
        ``half()`` is ``{0 | 1}``, matches that shape, and was reported
        infinitesimal.
        """
        return False

    def to_hyperset(self) -> Hyperset:
        """Ground this surreal number into a Kuratowski pair of left and right hypersets."""
        l_hypersets = [s.to_hyperset() for s in self.left]
        r_hypersets = [s.to_hyperset() for s in self.right]
        l_set = Hyperset.from_elements(*l_hypersets) if l_hypersets else EmptyHyperset()
        r_set = Hyperset.from_elements(*r_hypersets) if r_hypersets else EmptyHyperset()
        return pair(l_set, r_set)

    def to_float(self) -> float:
        """The value of this surreal, by Conway's simplicity rule.

        ``{L | R}`` is the *simplest* number strictly between ``max(L)`` and
        ``min(R)`` -- the one born earliest -- which is not the midpoint. The two
        agree on ``{0 | 1} = 1/2`` and disagree as soon as the interval is not
        centred on a simpler value: ``{0 | 4}`` is 1 and the midpoint is 2,
        ``{1/2 | }`` is 1 and the midpoint rule gave 1.5.

        Raises:
            ValueError: if ``max(L) >= min(R)``. Such a form is a *game* and not
                a number, and it has no value to return. ``{1 | 0}`` previously
                returned 0.5.
        """
        l_max = max((s.to_float() for s in self.left), default=None)
        r_min = min((s.to_float() for s in self.right), default=None)

        if l_max is not None and r_min is not None and l_max >= r_min:
            raise ValueError(
                f"max(L) = {l_max:g} is not below min(R) = {r_min:g}, so this "
                f"form is a game rather than a number and has no value"
            )
        return _simplest_between(l_max, r_min)

    def __repr__(self) -> str:
        return f"Surreal({self.to_float()})"


# Classical Calculus Bridges

def derivative_quotient(f: Callable[[float], float], x: float, h: float = 1e-7) -> float:
    """Compute classical derivative f'(x) using central differential quotient."""
    return (f(x + h) - f(x - h)) / (2.0 * h)


def riemann_integral(
    f: Callable[[float], float],
    a: float,
    b: float,
    subdivisions: int = 100,
) -> float:
    """Compute classical definite Riemann integral int_a^b f(x) dx using uniform partition."""
    if subdivisions <= 0:
        raise ValueError("Subdivisions must be positive")
    dx = (b - a) / subdivisions
    total = 0.0
    for i in range(subdivisions):
        mid = a + (i + 0.5) * dx
        total += f(mid) * dx
    return total


def symbolic_polynomial_derivative(coeffs: Sequence[GroundedRational]) -> list[GroundedRational]:
    """Exact rational derivative of polynomial P(x) = sum c_k x^k.

    coeffs is given in ascending degree order: [c0, c1, c2, ...].
    Returns [c1, 2*c2, 3*c3, ...].
    """
    if len(coeffs) <= 1:
        return [GroundedRational(0)]
    return [coeffs[k] * k for k in range(1, len(coeffs))]


def symbolic_polynomial_integral(
    coeffs: Sequence[GroundedRational],
    constant: GroundedRational | None = None,
) -> list[GroundedRational]:
    """Exact rational antiderivative int P(x) dx = C + sum (c_k / (k+1)) x^{k+1}."""
    c0 = constant if constant is not None else GroundedRational(0)
    result = [c0]
    for k, c in enumerate(coeffs):
        result.append(c / GroundedRational(k + 1))
    return result
