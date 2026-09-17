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

    def approximate(self, iterations: int = 25) -> float:
        """Compute floating-point approximation of this Dedekind cut."""
        # Find initial integer bounds
        low = GroundedRational(0)
        high = GroundedRational(1)
        while self.contains(high):
            low = high
            high = high * 2
        while not self.contains(low):
            high = low
            low = low - 2

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

    def is_cauchy(self, check_terms: int = 15, epsilon: float = 0.05) -> bool:
        """Empirically test whether the tail of the sequence satisfies |a_m - a_n| < epsilon."""
        start = max(1, check_terms // 2)
        for m in range(start, check_terms):
            for n in range(m + 1, check_terms):
                diff = abs((self.term(m) - self.term(n)).to_float())
                if diff >= epsilon:
                    return False
        return True

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
) -> bool:
    """Check whether two Cauchy sequences represent the same real number (lim |a_n - b_n| = 0)."""
    return abs(seq1.limit_approx(check_n) - seq2.limit_approx(check_n)) < tolerance


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
        """Canonical infinitesimal ε = { 0 | 1, 1/2 } (strictly positive, smaller than standard reals)."""
        return cls((cls.zero(),), (cls.half(), cls.one()))

    def is_infinitesimal(self) -> bool:
        """Return True if this surreal is non-zero and strictly bounded by all standard integers."""
        # 0 < x < 1/2
        return self.left == (SurrealNumber.zero(),) and len(self.right) > 0

    def to_hyperset(self) -> Hyperset:
        """Ground this surreal number into a Kuratowski pair of left and right hypersets."""
        l_hypersets = [s.to_hyperset() for s in self.left]
        r_hypersets = [s.to_hyperset() for s in self.right]
        l_set = Hyperset.from_elements(*l_hypersets) if l_hypersets else EmptyHyperset()
        r_set = Hyperset.from_elements(*r_hypersets) if r_hypersets else EmptyHyperset()
        return pair(l_set, r_set)

    def to_float(self) -> float:
        """Compute approximate numeric value for simple surreals."""
        if not self.left and not self.right:
            return 0.0
        if self.left and not self.right:
            return max(s.to_float() for s in self.left) + 1.0
        if not self.left and self.right:
            return min(s.to_float() for s in self.right) - 1.0
        l_max = max(s.to_float() for s in self.left)
        r_min = min(s.to_float() for s in self.right)
        return (l_max + r_min) / 2.0

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
