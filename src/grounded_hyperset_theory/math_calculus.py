"""Normal math calculus: Dedekind cuts, Cauchy sequences, and nonstandard analysis infinitesimals grounded in hyperset ordinals."""

from __future__ import annotations

import math
from typing import Callable, Iterable

from .hyperset import Hyperset, pair, von_neumann_ordinal
from .meta import _unpack_pair


def hyperset_integer(n: int) -> Hyperset:
    """Encode an integer as a Grothendieck equivalence pair of von Neumann ordinals."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"Integer expected, got {type(n).__name__}")
    if n >= 0:
        return pair(von_neumann_ordinal(n), von_neumann_ordinal(0))
    else:
        return pair(von_neumann_ordinal(0), von_neumann_ordinal(-n))


def hyperset_to_integer(h: Hyperset) -> int:
    """Decode a hyperset integer into a signed Python int."""
    pos_h, neg_h = _unpack_pair(h)
    return pos_h.to_int() - neg_h.to_int()


def hyperset_rational(p: int, q: int) -> Hyperset:
    """Encode a rational number p/q in lowest terms with q > 0 as a Hyperset."""
    if not isinstance(p, int) or not isinstance(q, int) or isinstance(p, bool) or isinstance(q, bool):
        raise TypeError("Numerator and denominator must be integers")
    if q == 0:
        raise ZeroDivisionError("Rational denominator cannot be zero")
    if q < 0:
        p, q = -p, -q
    g = math.gcd(abs(p), q)
    p //= g
    q //= g
    return pair(hyperset_integer(p), hyperset_integer(q))


def hyperset_to_rational(h: Hyperset) -> tuple[int, int]:
    """Decode a hyperset rational into an irreducible tuple (p, q) with q > 0."""
    p_h, q_h = _unpack_pair(h)
    p = hyperset_to_integer(p_h)
    q = hyperset_to_integer(q_h)
    if q <= 0:
        raise ValueError("Invalid rational: denominator must be strictly positive")
    return (p, q)


def rational_add(r1: Hyperset, r2: Hyperset) -> Hyperset:
    """Rational addition on hypersets: r1 + r2."""
    p1, q1 = hyperset_to_rational(r1)
    p2, q2 = hyperset_to_rational(r2)
    return hyperset_rational(p1 * q2 + p2 * q1, q1 * q2)


def rational_mul(r1: Hyperset, r2: Hyperset) -> Hyperset:
    """Rational multiplication on hypersets: r1 * r2."""
    p1, q1 = hyperset_to_rational(r1)
    p2, q2 = hyperset_to_rational(r2)
    return hyperset_rational(p1 * p2, q1 * q2)


def rational_lt(r1: Hyperset, r2: Hyperset) -> bool:
    """Strict ordering on hyperset rationals: r1 < r2."""
    p1, q1 = hyperset_to_rational(r1)
    p2, q2 = hyperset_to_rational(r2)
    return p1 * q2 < p2 * q1


class CauchySequenceHyperset:
    """A Cauchy sequence of rational numbers grounded in hyperset ordinals."""

    def __init__(
        self,
        term_fn: Callable[[int], tuple[int, int]],
    ) -> None:
        self.term_fn = term_fn

    def term(self, n: int) -> tuple[int, int]:
        """Evaluate the nth rational term in the Cauchy sequence."""
        if n < 0:
            raise ValueError("Term index must be non-negative")
        p, q = self.term_fn(n)
        g = math.gcd(abs(p), q)
        return (p // g, q // g)

    def term_hyperset(self, n: int) -> Hyperset:
        """Return the nth term as a hyperset rational."""
        p, q = self.term(n)
        return hyperset_rational(p, q)

    def to_hyperset(self, length: int = 8) -> Hyperset:
        """Objectify an initial segment of the sequence into an indexed Hyperset."""
        elements = [
            pair(von_neumann_ordinal(i), self.term_hyperset(i))
            for i in range(length)
        ]
        return Hyperset.from_elements(*elements)

    def is_cauchy(
        self,
        modulus_fn: Callable[[int], int],
        samples: int = 10,
        window: int = 5,
    ) -> bool:
        """Search for a violation of the Cauchy criterion; True if none is found.

        The two answers are not worth the same, and the caller needs to know
        which one they are holding.

        **False is conclusive.** A concrete pair ``(n_k, m)`` was found with
        ``|a_n_k - a_m| >= 1/k``, so ``modulus_fn`` is not a modulus of
        convergence for this sequence. That is a witness and it settles the
        question.

        **True is not a proof.** The criterion quantifies over *all* ``m >=
        n_k``; this checks ``window`` of them for ``samples`` values of ``k``. A
        sequence that is quiet across the sampled indices and then moves will
        pass. Raising ``samples`` and ``window`` makes passing mean more, and no
        finite choice makes it mean convergence.

        Args:
            modulus_fn: candidate modulus -- maps ``k`` to an index past which
                terms should stay within ``1/k`` of each other.
            samples: how many values of ``k`` to test, from 1 upward.
            window: how many terms past each ``modulus_fn(k)`` to compare.

        Raises:
            ValueError: if ``samples`` or ``window`` is not positive, or if
                ``modulus_fn`` returns a negative index. Each of those made the
                loop vacuous, and a vacuous loop returned True.
        """
        if samples < 1:
            raise ValueError(f"samples must be positive, got {samples}")
        if window < 1:
            raise ValueError(f"window must be positive, got {window}")
        for k in range(1, samples + 1):
            n_k = modulus_fn(k)
            if n_k < 0:
                raise ValueError(
                    f"modulus_fn({k}) returned {n_k}; a modulus must give a "
                    f"non-negative term index"
                )
            p_nk, q_nk = self.term(n_k)
            for m in range(n_k, n_k + window):
                p_m, q_m = self.term(m)
                # Check |p_nk/q_nk - p_m/q_m| < 1/k
                diff_num = abs(p_nk * q_m - p_m * q_nk)
                diff_den = q_nk * q_m
                if diff_num * k >= diff_den:
                    return False
        return True


class DedekindCutHyperset:
    """A real number represented as a Dedekind cut (L, R) of hyperset rationals."""

    def __init__(self, predicate_in_left: Callable[[int, int], bool]) -> None:
        self.predicate_in_left = predicate_in_left

    def contains_rational(self, p: int, q: int) -> bool:
        """Return True if rational p/q belongs to the left cut set L."""
        if q <= 0:
            raise ValueError("Denominator must be positive")
        return self.predicate_in_left(p, q)

    @classmethod
    def from_rational(cls, p: int, q: int) -> DedekindCutHyperset:
        """Construct the Dedekind cut for the rational p/q: L = {x in Q : x < p/q}."""
        return cls(lambda x_p, x_q: x_p * q < p * x_q)

    @classmethod
    def sqrt2(cls) -> DedekindCutHyperset:
        """Construct the Dedekind cut for sqrt(2): L = {x in Q : x <= 0 or x^2 < 2}."""
        def in_l(p: int, q: int) -> bool:
            if p <= 0:
                return True
            return p * p < 2 * q * q
        return cls(in_l)

    def to_hyperset(
        self,
        sample_range: range = range(-4, 5),
        denominators: tuple[int, ...] = (1, 2, 4),
    ) -> Hyperset:
        """Reify a discrete sample partition of the cut into a Hyperset pair (L, R)."""
        left_samples: list[Hyperset] = []
        right_samples: list[Hyperset] = []

        for den in denominators:
            for num in sample_range:
                g = math.gcd(abs(num), den)
                p, q = num // g, den // g
                r_h = hyperset_rational(p, q)
                if self.contains_rational(p, q):
                    left_samples.append(r_h)
                else:
                    right_samples.append(r_h)

        l_set = Hyperset.from_elements(*left_samples)
        r_set = Hyperset.from_elements(*right_samples)
        return pair(l_set, r_set)


class SurrealHyperset:
    """A Conway surreal number { X_L | X_R } grounded in hyperset ordinals."""

    def __init__(
        self,
        left: Iterable[SurrealHyperset] = (),
        right: Iterable[SurrealHyperset] = (),
    ) -> None:
        self.left = tuple(left)
        self.right = tuple(right)

    def __le__(self, other: SurrealHyperset) -> bool:
        """Conway order definition: x <= y iff no x_L >= y and no x >= y_R."""
        if not isinstance(other, SurrealHyperset):
            return NotImplemented
        for xl in self.left:
            if other <= xl:
                return False
        for yr in other.right:
            if yr <= self:
                return False
        return True

    def __lt__(self, other: SurrealHyperset) -> bool:
        if not isinstance(other, SurrealHyperset):
            return NotImplemented
        return self <= other and not (other <= self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SurrealHyperset):
            return NotImplemented
        return self <= other and other <= self

    def is_zero(self) -> bool:
        zero = SurrealHyperset()
        return self == zero

    def birthday_bound(self) -> int:
        """An upper bound on this value's birthday: the depth of its construction.

        Every value here is built from finite ``left`` and ``right`` tuples of
        values built the same way, so the recursion is finite and this
        terminates. A surreal of finite birthday is a dyadic rational, which is
        the fact the two predicates below rest on.
        """
        options = self.left + self.right
        return 1 + max((x.birthday_bound() for x in options), default=-1)

    def is_infinitesimal(self) -> bool:
        """Always False. No value this class can represent is infinitesimal.

        ``x`` is infinitesimal when ``0 < |x| < 1/n`` for *every* positive
        integer ``n``. ``left`` and ``right`` are finite tuples of values built
        the same way, so every representable value has a finite birthday, and a
        surreal of finite birthday is a dyadic rational ``p/2**k``. A non-zero
        one satisfies ``|x| >= 1/2**k``, so it is not below ``1/n`` once
        ``n > 2**k``. Reaching a genuine infinitesimal needs an infinite right
        set, which finite tuples cannot hold.

        This is a proof about the representation rather than a sampling budget,
        which is why it can return a constant without concealing anything.

        It previously compared against 1/2 alone and returned True for everything
        in ``(-1/2, 1/2)`` -- so 1/4 was reported infinitesimal -- while claiming
        the "for all n" quantifier in its own docstring. See
        ``surreal_infinitesimal``, which builds the finite approximants.
        """
        return False

    def is_infinite(self) -> bool:
        """Always False. No value this class can represent is infinite.

        By the same argument as ``is_infinitesimal``: a finite birthday forces a
        dyadic rational ``p/2**k``, which the integer ``abs(p) + 1`` exceeds. An
        infinite surreal such as omega needs an infinite left set.

        It previously tested ``3 < self``, so the integer 4 was reported
        infinite -- and ``surreal_omega(3)`` *is* the integer 4, so the
        truncation and the threshold cancelled and the answer looked right.
        """
        return False

    def to_hyperset(self) -> Hyperset:
        """Compile surreal number into a first-class Hyperset pair ({X_L}, {X_R})."""
        l_hypersets = [x.to_hyperset() for x in self.left]
        r_hypersets = [y.to_hyperset() for y in self.right]
        return pair(
            Hyperset.from_elements(*l_hypersets),
            Hyperset.from_elements(*r_hypersets),
        )


def surreal_zero() -> SurrealHyperset:
    """The surreal zero: { | }."""
    return SurrealHyperset()


def surreal_one() -> SurrealHyperset:
    """The surreal one: { 0 | }."""
    return SurrealHyperset(left=(surreal_zero(),))


def surreal_minus_one() -> SurrealHyperset:
    """The surreal minus one: { | 0 }."""
    return SurrealHyperset(right=(surreal_zero(),))


def surreal_infinitesimal(depth: int = 3) -> SurrealHyperset:
    """The ``depth``-th finite approximant to epsilon: the dyadic ``1/2**(depth+1)``.

    Epsilon is ``{ 0 | 1, 1/2, 1/4, ... }`` with an *infinite* right set. Cutting
    that set off at ``depth`` does not give a small infinitesimal, it gives an
    ordinary dyadic rational::

        surreal_infinitesimal(0) == 1/2      surreal_infinitesimal(3) == 1/16
        surreal_infinitesimal(1) == 1/4      surreal_infinitesimal(4) == 1/32

    so ``surreal_infinitesimal(d).is_infinitesimal()`` is False, correctly. Each
    term is below the last and none of them is infinitesimal; the limit is not a
    member of the sequence and is not representable here.

    The name is released public API and is kept; what it returns is unchanged.
    """
    z = surreal_zero()
    rights: list[SurrealHyperset] = [surreal_one()]
    curr = surreal_one()
    for _ in range(depth):
        curr = SurrealHyperset(left=(z,), right=(curr,))
        rights.append(curr)
    return SurrealHyperset(left=(z,), right=tuple(rights))


def surreal_omega(depth: int = 3) -> SurrealHyperset:
    """The ``depth``-th finite approximant to omega: the integer ``depth + 1``.

    Omega is ``{ 0, 1, 2, ... | }`` with an *infinite* left set. Cutting that set
    off at ``depth`` gives ``{0, 1, ..., depth | }``, and by the simplicity rule
    that is the integer ``depth + 1``. ``surreal_omega(3)`` is 4, not a
    transfinite value, so ``surreal_omega(d).is_infinite()`` is False, correctly;
    it used to be True for ``d >= 3`` only because the value it was compared
    against was the integer 3.

    The name is released public API and is kept; what it returns is unchanged.
    """
    lefts: list[SurrealHyperset] = [surreal_zero()]
    curr = surreal_zero()
    for _ in range(depth):
        curr = SurrealHyperset(left=(curr,))
        lefts.append(curr)
    return SurrealHyperset(left=tuple(lefts))


def hyperset_derivative_sequence(
    f: Callable[[tuple[int, int]], tuple[int, int]],
    x: tuple[int, int],
) -> CauchySequenceHyperset:
    """Construct the Cauchy sequence of difference quotients [f(x+h_k) - f(x)] / h_k where h_k = 1/2^(k+1)."""
    x_p, x_q = x

    def term(k: int) -> tuple[int, int]:
        h_den = 1 << (k + 1)  # h = 1 / 2^(k+1)
        # x + h = (x_p * h_den + x_q) / (x_q * h_den)
        xh_p = x_p * h_den + x_q
        xh_q = x_q * h_den

        f_xh_p, f_xh_q = f((xh_p, xh_q))
        f_x_p, f_x_q = f((x_p, x_q))

        # [f(x+h) - f(x)] / h = [f(x+h) - f(x)] * h_den
        num = (f_xh_p * f_x_q - f_x_p * f_xh_q) * h_den
        den = f_xh_q * f_x_q
        g = math.gcd(abs(num), den)
        return (num // g, den // g)

    return CauchySequenceHyperset(term)
