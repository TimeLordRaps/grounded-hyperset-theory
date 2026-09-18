"""Checks that could only ever answer "yes", and the claims they were supporting.

Two modules bridge hypersets to classical analysis, and between them they had
eight places where a predicate reported a property it had not established:

- `is_cauchy` inspected a contiguous window of early terms, so a sequence that is
  identically zero until n = 15 and equal to n afterwards was certified Cauchy.
- `are_equivalent_cauchy` is documented `lim |a_n - b_n| = 0` and compared one
  term, so `pi_leibniz` and a constant sequence 0.0476 from pi were the same real.
- `SurrealNumber.to_float` took the midpoint of the option interval, where the
  surreal value is the *simplest* number in it: `{0 | 4}` is 1, not 2.
- Both `is_infinitesimal` implementations reported values that are plainly not
  infinitesimal -- 1/2 in one module, 1/4 in the other.
- `is_infinite` tested "greater than 3", and `surreal_omega(3)` is the integer 4,
  so a truncation and a threshold cancelled into a confident wrong answer.
- `DedekindCut.approximate` did not terminate on the empty or the full cut.

The distinction the fixes turn on: **a refutation is a proof and a passing search
is not.** Where a property cannot be decided, the code now says which of the two
answers it is handing back. Where it *can* be decided -- no value built from
finite option tuples is infinitesimal or infinite, because it has finite birthday
and is therefore a dyadic rational -- a constant is returned with the argument
written out, which is a proof rather than an unfinished search.

Run against the unfixed sources, 36 of these 66 fail and two more never finish:
the empty-cut and full-cut cases hang the run rather than failing it, which is
the defect they are about. The `negative_control` tests reproduce the replaced
logic so the gap stays legible after the fact.
"""

from __future__ import annotations

import math

import pytest

from grounded_hyperset_theory.math_calculus import (
    CauchySequenceHyperset,
    SurrealHyperset,
    surreal_infinitesimal,
    surreal_omega,
    surreal_one,
    surreal_zero,
)
from grounded_hyperset_theory.real_analysis_bridge import (
    CauchySequence,
    DedekindCut,
    GroundedRational,
    SurrealNumber,
    are_equivalent_cauchy,
    symbolic_polynomial_derivative,
    symbolic_polynomial_integral,
)


def sleeper_sequence() -> CauchySequence:
    """Zero over the whole window the old check inspected, then unbounded."""
    return CauchySequence(
        term_fn=lambda n: GroundedRational(0) if n < 15 else GroundedRational(n),
        name="zero until 15, then n",
    )


def dyadic(k: int) -> SurrealHyperset:
    """The surreal 1/2**k, as {0 | 1/2**(k-1)}."""
    current = surreal_one()
    for _ in range(k):
        current = SurrealHyperset(left=(surreal_zero(),), right=(current,))
    return current


def integer(n: int) -> SurrealHyperset:
    """The surreal integer n, as {n-1 | }."""
    current = surreal_zero()
    for _ in range(n):
        current = SurrealHyperset(left=(current,))
    return current


# ============================================================================
# 1. A sequence that is not Cauchy must not be certified Cauchy
# ============================================================================


def test_a_sequence_that_explodes_past_the_window_is_caught() -> None:
    assert sleeper_sequence().is_cauchy() is False


def test_the_witness_names_the_pair_that_refutes_it() -> None:
    violation = sleeper_sequence().cauchy_violation()
    assert violation is not None
    m, n, gap = violation
    assert gap >= 0.05
    assert {m, n} & {15, 30, 60, 120}, "the witness comes from past the window"


def test_negative_control_the_contiguous_window_saw_nothing() -> None:
    # The replaced body: m, n both inside range(check_terms // 2, check_terms).
    sequence = sleeper_sequence()
    for m in range(7, 15):
        for n in range(m + 1, 15):
            assert abs((sequence.term(m) - sequence.term(n)).to_float()) < 0.05
    # ... while the sequence is unbounded.
    assert sequence.term(1000).to_float() == 1000.0


def test_a_genuinely_cauchy_sequence_still_passes() -> None:
    # Rejecting a convergent sequence would be a real cost, so check it is not paid.
    assert CauchySequence.geometric(GroundedRational(1, 2)).is_cauchy() is True
    assert CauchySequence.euler_e().is_cauchy() is True


def test_a_constant_sequence_has_no_violation() -> None:
    constant = CauchySequence(term_fn=lambda n: GroundedRational(3), name="3")
    assert constant.cauchy_violation() is None


def test_a_linearly_growing_sequence_is_refuted() -> None:
    linear = CauchySequence(term_fn=lambda n: GroundedRational(n), name="n")
    assert linear.is_cauchy() is False


def test_a_slowly_divergent_sequence_still_passes_and_that_is_documented() -> None:
    # ln(n)/100 diverges, and its increments are below epsilon across everything
    # sampled. This is not a bug being pinned as correct: it is the stated limit
    # of the check, recorded so the True answer is never mistaken for a proof.
    slow = CauchySequence(
        term_fn=lambda n: GroundedRational(int(round(math.log(n + 2) * 1000)), 100_000),
        name="ln(n)/100",
    )
    assert slow.is_cauchy() is True
    assert slow.term(10**100).to_float() > 10 * slow.term(10**6).to_float() > 0.0
    # It is refutable by asking harder, which is what the parameters are for.
    assert slow.is_cauchy(check_terms=15, epsilon=0.001) is False


@pytest.mark.parametrize("kwargs", [
    {"check_terms": 1},
    {"epsilon": 0.0},
    {"epsilon": -1.0},
    {"reach": -1},
])
def test_parameters_that_would_make_the_search_vacuous_are_refused(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        sleeper_sequence().cauchy_violation(**kwargs)


# ============================================================================
# 2. Two different reals must not be called the same real
# ============================================================================


def test_pi_and_a_constant_at_its_twentieth_term_are_not_equivalent() -> None:
    pi_sequence = CauchySequence.pi_leibniz()
    at_twenty = pi_sequence.limit_approx(20)
    constant = CauchySequence(
        term_fn=lambda n, v=at_twenty: GroundedRational(int(v * 10**9), 10**9),
        name="constant",
    )
    assert abs(at_twenty - math.pi) > 0.04, "the two limits really are far apart"
    assert are_equivalent_cauchy(pi_sequence, constant) is False


def test_negative_control_comparing_one_term_called_them_equal() -> None:
    # The replaced body, reproduced.
    pi_sequence = CauchySequence.pi_leibniz()
    at_twenty = pi_sequence.limit_approx(20)
    constant = CauchySequence(
        term_fn=lambda n, v=at_twenty: GroundedRational(int(v * 10**9), 10**9),
        name="constant",
    )
    single_term = abs(pi_sequence.limit_approx(20) - constant.limit_approx(20)) < 1e-3
    assert single_term is True, "identical at the one index that was compared"


def test_a_sequence_is_equivalent_to_itself() -> None:
    assert are_equivalent_cauchy(CauchySequence.euler_e(), CauchySequence.euler_e()) is True


def test_two_routes_to_the_same_limit_are_equivalent() -> None:
    # Both converge to 2: the geometric series and a sequence approaching from above.
    geometric = CauchySequence.geometric(GroundedRational(1, 2))
    other = CauchySequence(
        term_fn=lambda n: GroundedRational(2) + GroundedRational(1, 2 ** (n + 1)),
        name="2 + 2^-n",
    )
    assert are_equivalent_cauchy(geometric, other, tolerance=1e-2) is True


def test_a_negative_tail_is_refused() -> None:
    e = CauchySequence.euler_e()
    with pytest.raises(ValueError, match="non-negative"):
        are_equivalent_cauchy(e, e, tail=-1)


# ============================================================================
# 3. The surreal value is the simplest option, not the midpoint
# ============================================================================


@pytest.mark.parametrize("left, right, expected", [
    ((), (), 0.0),
    (("zero",), (), 1.0),
    ((), ("zero",), -1.0),
    (("zero",), ("one",), 0.5),
])
def test_the_canonical_small_surreals_are_unchanged(left, right, expected) -> None:
    table = {"zero": SurrealNumber.zero(), "one": SurrealNumber.one()}
    value = SurrealNumber(tuple(table[k] for k in left), tuple(table[k] for k in right))
    assert value.to_float() == expected


def test_the_simplest_number_between_zero_and_four_is_one() -> None:
    four = SurrealNumber((SurrealNumber((SurrealNumber((SurrealNumber.one(),), ()),), ()),), ())
    assert four.to_float() == 4.0
    assert SurrealNumber((SurrealNumber.zero(),), (four,)).to_float() == 1.0


def test_the_simplest_number_above_one_half_is_one() -> None:
    assert SurrealNumber((SurrealNumber.half(),), ()).to_float() == 1.0


def test_negative_control_the_midpoint_rule_gave_different_answers() -> None:
    # The replaced body, on the two cases above.
    assert (0.0 + 4.0) / 2.0 == 2.0, "midpoint of {0 | 4}, where the value is 1"
    assert 0.5 + 1.0 == 1.5, "midpoint rule on {1/2 | }, where the value is 1"


def test_a_form_whose_options_cross_is_a_game_and_is_refused() -> None:
    # {1 | 0} is not a number. It used to return 0.5.
    game = SurrealNumber((SurrealNumber.one(),), (SurrealNumber.zero(),))
    with pytest.raises(ValueError, match="game rather than a number"):
        game.to_float()


def test_a_form_whose_options_touch_is_also_refused() -> None:
    game = SurrealNumber((SurrealNumber.zero(),), (SurrealNumber.zero(),))
    with pytest.raises(ValueError, match="game rather than a number"):
        game.to_float()


def test_values_stay_ordered_by_their_option_intervals() -> None:
    zero, one, half = SurrealNumber.zero(), SurrealNumber.one(), SurrealNumber.half()
    quarter = SurrealNumber((zero,), (half,))
    assert quarter.to_float() < half.to_float() < one.to_float()
    assert quarter.to_float() == 0.25


# ============================================================================
# 4. Nothing here is infinitesimal, and nothing here is infinite
# ============================================================================


def test_one_half_is_not_infinitesimal() -> None:
    assert SurrealNumber.half().is_infinitesimal() is False


def test_the_value_named_infinitesimal_is_one_quarter() -> None:
    eps = SurrealNumber.infinitesimal()
    assert eps.to_float() == 0.25
    assert eps.is_infinitesimal() is False


def test_negative_control_the_shape_test_matched_one_half() -> None:
    # The replaced body: a statement about the expression, not about its value.
    half = SurrealNumber.half()
    assert half.left == (SurrealNumber.zero(),) and len(half.right) > 0
    assert half.to_float() == 0.5, "which is not infinitesimal"


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_no_dyadic_is_infinitesimal(k: int) -> None:
    assert dyadic(k).is_infinitesimal() is False


@pytest.mark.parametrize("depth", [0, 1, 2, 3, 4])
def test_the_infinitesimal_constructor_builds_an_ordinary_dyadic(depth: int) -> None:
    # surreal_infinitesimal(d) truncates eps's infinite right set at d, and the
    # truncation is exactly 1/2**(d+1).
    assert surreal_infinitesimal(depth) == dyadic(depth + 1)
    assert surreal_infinitesimal(depth).is_infinitesimal() is False


@pytest.mark.parametrize("depth", [0, 1, 2, 3, 4])
def test_the_omega_constructor_builds_an_ordinary_integer(depth: int) -> None:
    assert surreal_omega(depth) == integer(depth + 1)
    assert surreal_omega(depth).is_infinite() is False


@pytest.mark.parametrize("n", [4, 5, 9, 20])
def test_an_integer_above_three_is_not_infinite(n: int) -> None:
    assert integer(n).is_infinite() is False


def test_negative_control_the_threshold_was_the_integer_three() -> None:
    # The replaced body, and why it looked right: surreal_omega(3) is 4, and 4
    # is above the threshold, so the truncation and the threshold cancelled.
    assert integer(3) < integer(4)
    assert surreal_omega(3) == integer(4)


def test_the_birthday_bound_is_finite_and_that_is_the_whole_argument() -> None:
    # Finite birthday implies dyadic rational implies neither infinitesimal nor
    # infinite. The bound being finite is what makes the constant answers proofs.
    for value in (surreal_zero(), surreal_one(), dyadic(5), integer(6), surreal_omega(4)):
        assert 0 <= value.birthday_bound() < 100


# ============================================================================
# 5. The Conway order underneath is correct, which is why the rest is fixable
# ============================================================================


def test_the_order_on_integers_agrees_with_the_integers() -> None:
    ints = [integer(n) for n in range(6)]
    assert all((ints[a] < ints[b]) == (a < b) for a in range(6) for b in range(6))


def test_equality_on_integers_is_integer_equality() -> None:
    ints = [integer(n) for n in range(6)]
    assert all((ints[a] == ints[b]) == (a == b) for a in range(6) for b in range(6))


def test_the_order_on_dyadics_agrees_with_the_rationals() -> None:
    assert all(
        (dyadic(a) < dyadic(b)) == (1 / 2 ** a < 1 / 2 ** b)
        for a in range(5)
        for b in range(5)
    )


# ============================================================================
# 6. A cut that is not a cut must not be approximated forever
# ============================================================================


def test_the_empty_cut_refuses_instead_of_running_forever() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        DedekindCut(lambda q: False, name="empty").approximate()


def test_the_full_cut_refuses_instead_of_running_forever() -> None:
    with pytest.raises(ValueError, match="non-empty complement"):
        DedekindCut(lambda q: True, name="full").approximate()


def test_the_real_cuts_still_approximate_correctly() -> None:
    assert abs(DedekindCut.sqrt_two().approximate() - math.sqrt(2)) < 1e-6
    assert abs(DedekindCut.golden_ratio().approximate() - (1 + math.sqrt(5)) / 2) < 1e-6
    assert abs(DedekindCut.from_rational(GroundedRational(7, 4)).approximate() - 1.75) < 1e-6


def test_a_negative_real_is_bracketed_downward() -> None:
    cut = DedekindCut.from_rational(GroundedRational(-11, 2))
    assert abs(cut.approximate() - (-5.5)) < 1e-6


def test_a_predicate_that_is_not_downward_closed_has_a_witness() -> None:
    # {q : q^2 < 2} is the interval (-sqrt2, sqrt2), not a lower cut.
    not_a_cut = DedekindCut(lambda q: q * q < GroundedRational(2), name="q^2 < 2")
    violation = not_a_cut.downward_closure_violation()
    assert violation is not None
    low, high = violation
    assert low < high
    assert not_a_cut.contains(high) and not not_a_cut.contains(low)


@pytest.mark.parametrize("cut", [
    DedekindCut.sqrt_two(),
    DedekindCut.golden_ratio(),
    DedekindCut.from_rational(GroundedRational(3, 2)),
])
def test_the_genuine_cuts_have_no_downward_closure_witness(cut: DedekindCut) -> None:
    assert cut.downward_closure_violation() is None


# ============================================================================
# 7. The exact operations, which were right and stay right
# ============================================================================


def test_differentiating_the_antiderivative_recovers_the_polynomial() -> None:
    coefficients = [GroundedRational(3), GroundedRational(-1, 2),
                    GroundedRational(7, 3), GroundedRational(5)]
    recovered = symbolic_polynomial_derivative(symbolic_polynomial_integral(coefficients))
    assert [str(c) for c in recovered] == [str(c) for c in coefficients]


def test_the_derivative_of_a_constant_is_zero() -> None:
    assert [str(c) for c in symbolic_polynomial_derivative([GroundedRational(7)])] == ["ℚ(0)"]


def test_the_cauchy_hyperset_modulus_check_refuses_a_vacuous_window() -> None:
    sequence = CauchySequenceHyperset(lambda n: (1, n + 1))
    with pytest.raises(ValueError, match="positive"):
        sequence.is_cauchy(lambda k: k, samples=0)
    with pytest.raises(ValueError, match="positive"):
        sequence.is_cauchy(lambda k: k, window=0)


def test_the_cauchy_hyperset_modulus_check_refuses_a_negative_index() -> None:
    sequence = CauchySequenceHyperset(lambda n: (1, n + 1))
    with pytest.raises(ValueError, match="non-negative term index"):
        sequence.is_cauchy(lambda k: -k)


def test_a_real_modulus_is_accepted_and_a_wrong_one_is_refuted() -> None:
    # 1/(n+1) is within 1/k of its tail once n >= 2k.
    sequence = CauchySequenceHyperset(lambda n: (1, n + 1))
    assert sequence.is_cauchy(lambda k: 2 * k) is True
    # n is not Cauchy under any modulus.
    diverging = CauchySequenceHyperset(lambda n: (n, 1))
    assert diverging.is_cauchy(lambda k: 2 * k) is False
