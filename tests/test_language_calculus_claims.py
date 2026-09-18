"""What `language_calculus` claims about regular expressions, and whether it holds.

Three claims are under test. The first is Brzozowski's theorem itself: the set of
derivatives of a regular expression is finite, so the automaton built from them
terminates. That holds only *modulo similarity* -- associativity, commutativity
and idempotence of union -- and the implementation had only idempotence, and only
between structurally identical operands. `(a|b)*ab(a|b)*` is an ordinary regular
expression with a three-state minimal DFA, and it did not converge: 65 states at a
budget of 64, 257 at 256, and a RecursionError from `Regex.__repr__` on the way.

The second is that `max_states` is a budget. It was checked once per dequeued
state while the inner loop over the alphabet inserted without rechecking, so a cap
of 64 produced 65 states -- neither the true size nor the cap -- and the result was
a graph with states that had no outgoing transitions, which is indistinguishable
from states that reject every continuation. A truncated automaton is not an
automaton, and nothing said it had been truncated.

The third is the word "minimal" in `dfa_apg`'s docstring. Derivatives modulo ACI
give an automaton with no unreachable states; that is not minimality, and the
counterexamples are pinned below so the docstring cannot drift back.

The reference used throughout is `_accepts`, a matcher written from the language
semantics of each operator rather than from `derivative`, and `_nerode_classes`,
which counts residual languages directly. Neither consults the implementation, so
a disagreement points at one side rather than at a shared assumption.

Negative control: run as a whole against the unfixed source, 20 of these 99 tests
fail and two more never finish. The two that hang are the ones about
non-termination -- `test_the_divergent_regex_now_converges` and the finiteness
check for `(a|b)*ab(a|b)*` -- so they stop the run rather than failing it, which
is the defect rather than a gap in the control. Counted with those two
deselected: 20 failed, 77 passed.
"""

from __future__ import annotations

import itertools

import pytest

from grounded_hyperset_theory.language_calculus import Regex, dfa_apg, dfa_hyperset
from grounded_hyperset_theory.hyperset import Hyperset

A = Regex.lit("a")
B = Regex.lit("b")
C = Regex.lit("c")
AB = A.union(B)
ALPHA = "ab"


# --------------------------------------------------------------------------
# References, written from the definitions and not from the implementation.
# --------------------------------------------------------------------------


def _accepts(r: Regex, w: str) -> bool:
    """Whether `w` is in L(r), from the meaning of each operator."""
    if r.kind == "empty":
        return False
    if r.kind == "eps":
        return w == ""
    if r.kind == "lit":
        return w == r.val
    if r.kind == "union":
        return _accepts(r.left, w) or _accepts(r.right, w)
    if r.kind == "concat":
        return any(
            _accepts(r.left, w[:i]) and _accepts(r.right, w[i:])
            for i in range(len(w) + 1)
        )
    if r.kind == "star":
        if w == "":
            return True
        return any(
            _accepts(r.left, w[:i]) and _accepts(r, w[i:])
            for i in range(1, len(w) + 1)
        )
    raise AssertionError(f"unknown kind {r.kind!r}")


def _words(alphabet: str, upto: int):
    for n in range(upto + 1):
        for t in itertools.product(alphabet, repeat=n):
            yield "".join(t)


def _nerode_classes(r: Regex, alphabet: str = ALPHA) -> int:
    """The number of distinct residual languages, i.e. the minimal DFA's size.

    Two prefixes are in the same Myhill-Nerode class when they admit the same
    continuations. Computed from the language, so it needs no reference
    automaton; exact for the small languages used here.
    """
    tests = list(_words(alphabet, 6))
    return len({tuple(_accepts(r, p + t) for t in tests) for p in _words(alphabet, 4)})


def _derivative_closure(r: Regex, alphabet: str = ALPHA) -> set[Regex]:
    """Every derivative reachable from `r`, with no budget. Terminates only if
    the normalisation really does make the set finite -- which is the point."""
    seen = {r}
    frontier = [r]
    while frontier:
        curr = frontier.pop()
        for ch in alphabet:
            d = curr.derivative(ch)
            if d not in seen:
                seen.add(d)
                frontier.append(d)
    return seen


# --------------------------------------------------------------------------
# 1. Union is normalised modulo A, C and I -- the premise of the whole thing.
# --------------------------------------------------------------------------


def test_union_is_commutative_as_a_value() -> None:
    """`a|b` and `b|a` must be the same object, not merely the same language.

    Sameness as a value is what makes them one DFA state instead of two.
    """
    assert A.union(B) == B.union(A)


def test_union_is_associative_as_a_value() -> None:
    assert A.union(B).union(C) == A.union(B.union(C))


def test_union_is_idempotent_across_nesting() -> None:
    """Idempotence between structurally identical operands was already there.
    What was missing is idempotence of an operand against one buried in a nest."""
    assert A.union(A) == A
    assert A.union(B).union(A) == A.union(B)
    assert A.union(B).union(B.union(A)) == A.union(B)


def test_the_empty_language_is_absorbed_from_either_side() -> None:
    empty = Regex.empty()
    assert A.union(empty) == A
    assert empty.union(A) == A
    assert empty.union(empty) == empty


def test_a_union_of_the_same_operands_is_the_same_value_whatever_the_build_order() -> None:
    """Five spellings of a|b|c. All five are one value, so one DFA state."""
    spellings = [
        A.union(B).union(C),
        A.union(C).union(B),
        C.union(B).union(A),
        A.union(B.union(C)),
        B.union(C).union(A.union(B)),
    ]
    assert len(set(spellings)) == 1, sorted(str(s) for s in set(spellings))


def test_normalisation_does_not_change_the_language() -> None:
    """The point of ACI is that it is sound: the normal form denotes the same
    language as the expression it replaced. Checked against `_accepts` rather
    than assumed from the algebra."""
    pairs = [
        (A.union(B), B.union(A)),
        (A.union(B).union(C), A.union(B.union(C))),
        (A.union(A), A),
        (A.union(Regex.empty()), A),
        (A.concat(B).union(B.concat(A)), B.concat(A).union(A.concat(B))),
    ]
    for left, right in pairs:
        for w in _words("abc", 4):
            assert _accepts(left, w) == _accepts(right, w), (str(left), str(right), w)


def test_the_normal_form_is_deterministic_across_repeated_construction() -> None:
    """Sorting is by a structural key, so it must not depend on hash randomisation
    or on object identity. Same inputs, same arrangement, every time."""
    first = str(B.union(C).union(A))
    for _ in range(50):
        assert str(B.union(C).union(A)) == first


def test_the_sort_key_is_structural_and_not_textual() -> None:
    """A textual key would call `repr`, and `repr` on a deep derivative is exactly
    what used to raise RecursionError. Ordering a deep expression must not."""
    deep = A
    for _ in range(400):
        deep = deep.concat(A)
    ordered = B.union(deep)  # must not recurse through repr
    assert ordered.kind == "union"


# --------------------------------------------------------------------------
# 2. The two semantics that were already right, kept right.
# --------------------------------------------------------------------------

_CASES: dict[str, Regex] = {
    "a": A,
    "a|b": AB,
    "ab": A.concat(B),
    "a*": A.star(),
    "(a|b)*": AB.star(),
    "(a|b)*a": AB.star().concat(A),
    "(a|b)*a(a|b)": AB.star().concat(A).concat(AB),
    "(a|b)*a(a|b)(a|b)": AB.star().concat(A).concat(AB).concat(AB),
    "a*b*": A.star().concat(B.star()),
    "(ab)*": A.concat(B).star(),
    "a(a|b)|b(b|a)": A.concat(AB).union(B.concat(B.union(A))),
    "(a*b*)*": A.star().concat(B.star()).star(),
    "(a|b)*ab(a|b)*": AB.star().concat(A).concat(B).concat(AB.star()),
}


@pytest.mark.parametrize("name", sorted(_CASES))
def test_is_nullable_agrees_with_the_empty_word_being_in_the_language(name: str) -> None:
    assert _CASES[name].is_nullable == _accepts(_CASES[name], ""), name


@pytest.mark.parametrize("name", sorted(_CASES))
def test_the_derivative_agrees_with_its_definition(name: str) -> None:
    """L(D_a(r)) = {w : aw in L(r)}, checked word by word.

    This is the property ACI normalisation must not disturb: it collapses
    distinct spellings, and it would be a real defect if it collapsed distinct
    languages.
    """
    r = _CASES[name]
    for ch in ALPHA:
        d = r.derivative(ch)
        for w in _words(ALPHA, 5):
            assert _accepts(d, w) == _accepts(r, ch + w), (name, ch, w)


# --------------------------------------------------------------------------
# 3. Finiteness -- Brzozowski's theorem, which needs the normalisation above.
# --------------------------------------------------------------------------


def test_the_divergent_regex_now_converges() -> None:
    """`(a|b)*ab(a|b)*` used to produce a state for every budget it was given.

    Without ACI the derivative set is infinite, so this did not fail against the
    unfixed source -- it ran until the budget, returned budget+1 states, and for
    a large budget raised RecursionError from `__repr__` while labelling a node.
    """
    divergent = _CASES["(a|b)*ab(a|b)*"]
    closure = _derivative_closure(divergent)
    assert len(closure) == 6, len(closure)
    apg = dfa_apg(divergent, ALPHA, max_states=64)
    assert len(apg.nodes) == 6


@pytest.mark.parametrize("name", sorted(_CASES))
def test_the_derivative_set_is_finite_and_the_automaton_is_exactly_it(name: str) -> None:
    """The built state set is the derivative closure: no fewer (which would be a
    truncation) and no more (which would be unreachable states)."""
    r = _CASES[name]
    closure = _derivative_closure(r)
    apg = dfa_apg(r, ALPHA, max_states=4096)
    assert len(apg.nodes) == len(closure), (name, len(apg.nodes), len(closure))


@pytest.mark.parametrize("name", sorted(_CASES))
def test_every_state_has_an_outgoing_transition(name: str) -> None:
    """A DFA state has a transition for every letter, so in a two-letter alphabet
    every node has at least one successor. The truncated automaton broke this:
    states left in the queue had none, and a state with no successors reads as a
    state that rejects everything.
    """
    apg = dfa_apg(_CASES[name], ALPHA, max_states=4096)
    dead = [n for n in apg.nodes if not apg.children(n)]
    assert dead == [], (name, [str(n) for n in dead])


def test_a_deep_derivative_can_still_be_printed() -> None:
    """`dfa_apg` labels every node with `str(derivative)`. Under the old
    representation the derivatives of `(a|b)*ab(a|b)*` nested past the recursion
    limit, so building the automaton raised RecursionError rather than returning.
    """
    apg = dfa_apg(_CASES["(a|b)*ab(a|b)*"], ALPHA, max_states=64)
    labels = [str(n.label) for n in apg.nodes]
    assert all(labels)
    assert len(labels) == 6


# --------------------------------------------------------------------------
# 4. The budget: refuse, do not truncate.
# --------------------------------------------------------------------------


def test_the_budget_refuses_rather_than_returning_a_partial_automaton() -> None:
    big = _CASES["(a|b)*a(a|b)(a|b)"]
    assert len(dfa_apg(big, ALPHA, max_states=4096).nodes) == 8
    with pytest.raises(ValueError, match="max_states"):
        dfa_apg(big, ALPHA, max_states=4)


def test_the_refusal_says_what_to_do_about_it() -> None:
    with pytest.raises(ValueError) as excinfo:
        dfa_apg(_CASES["(a|b)*a(a|b)(a|b)"], ALPHA, max_states=2)
    message = str(excinfo.value)
    assert "max_states=2" in message
    assert "raise the budget" in message
    assert "partial automaton" in message


@pytest.mark.parametrize("cap", [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 64])
def test_the_result_never_exceeds_the_budget(cap: int) -> None:
    """The cap was tested once per dequeued state while the inner loop inserted
    freely, so `max_states=64` came back with 65 states and `max_states=256` with
    257. Whatever the cap, either the answer fits in it or there is no answer.
    """
    big = _CASES["(a|b)*a(a|b)(a|b)"]
    try:
        apg = dfa_apg(big, ALPHA, max_states=cap)
    except ValueError:
        assert cap < 8
        return
    assert len(apg.nodes) <= cap, (cap, len(apg.nodes))


def test_a_budget_exactly_equal_to_the_state_count_succeeds() -> None:
    """The boundary the off-by-one lived on. Eight states must fit in eight."""
    big = _CASES["(a|b)*a(a|b)(a|b)"]
    assert len(dfa_apg(big, ALPHA, max_states=8).nodes) == 8
    with pytest.raises(ValueError):
        dfa_apg(big, ALPHA, max_states=7)


@pytest.mark.parametrize("cap", [0, -1, -64])
def test_a_budget_below_one_is_rejected(cap: int) -> None:
    """`max_states=0` cannot describe any automaton -- the root state alone needs
    one. It used to return a lone root node with no transitions at all."""
    with pytest.raises(ValueError, match="at least 1"):
        dfa_apg(A, ALPHA, max_states=cap)


def test_the_hyperset_form_refuses_on_the_same_terms() -> None:
    """`dfa_hyperset` grounds whatever `dfa_apg` returns, so a truncation there
    became a hyperset built from a non-automaton, with no sign of it."""
    big = _CASES["(a|b)*a(a|b)(a|b)"]
    assert isinstance(dfa_hyperset(big, ALPHA, max_states=64), Hyperset)
    with pytest.raises(ValueError, match="max_states"):
        dfa_hyperset(big, ALPHA, max_states=4)


# --------------------------------------------------------------------------
# 5. Minimality: the claim that was withdrawn, pinned so it stays withdrawn.
# --------------------------------------------------------------------------


def test_the_docstring_no_longer_claims_minimality() -> None:
    doc = dfa_apg.__doc__ or ""
    assert "minimal" in doc, "the relationship to the minimal DFA should be stated"
    assert "**not** the same as minimal" in doc


@pytest.mark.parametrize(
    ("name", "built", "minimal"),
    [
        ("(a*b*)*", 3, 1),
        ("(a|b)*ab(a|b)*", 6, 3),
    ],
)
def test_the_automaton_is_not_minimal_and_here_is_how_far_off(
    name: str, built: int, minimal: int
) -> None:
    """Two measured counterexamples to the withdrawn claim.

    `(a*b*)*` denotes every string over {a,b}, so one state suffices and three
    are built. Both numbers are pinned: if a future minimisation pass lands, this
    test fails and the docstring gets revisited rather than silently outliving
    its evidence.
    """
    r = _CASES[name]
    assert len(dfa_apg(r, ALPHA, max_states=4096).nodes) == built
    assert _nerode_classes(r) == minimal


def test_normalisation_makes_one_previously_non_minimal_case_minimal() -> None:
    """`a(a|b) | b(b|a)` built five states for a four-state language, because the
    two `(a|b)` derivatives were spelled differently. Under ACI they are one
    state. Recorded as a gain, not as a general minimality guarantee -- the two
    cases above are still off."""
    r = _CASES["a(a|b)|b(b|a)"]
    assert len(dfa_apg(r, ALPHA, max_states=4096).nodes) == 4
    assert _nerode_classes(r) == 4


@pytest.mark.parametrize("name", sorted(_CASES))
def test_the_automaton_is_never_smaller_than_the_minimal_one(name: str) -> None:
    """The weaker claim that does hold everywhere, and the one worth relying on:
    no unreachable states, so the count is between the minimum and the closure.
    A build below the Myhill-Nerode count would mean states had been merged that
    denote different languages."""
    r = _CASES[name]
    assert len(dfa_apg(r, ALPHA, max_states=4096).nodes) >= _nerode_classes(r), name


# --------------------------------------------------------------------------
# 6. The existing behaviour these changes had to preserve.
# --------------------------------------------------------------------------


def test_the_starred_language_still_grounds_to_a_non_well_founded_hyperset() -> None:
    """`(a|b)*a` has a cycle in its automaton, which is the whole reason this
    module grounds DFAs into hypersets: a looping automaton is a non-well-founded
    set. That regex builds two states either way, so the normalisation must leave
    this exactly as it was."""
    reg = AB.star().concat(A)
    apg = dfa_apg(reg, alphabet=ALPHA, max_states=16)
    assert apg.has_cycles()
    grounded = dfa_hyperset(reg, alphabet=ALPHA, max_states=16)
    assert isinstance(grounded, Hyperset)
    assert not grounded.is_well_founded


def test_even_a_finite_language_grounds_to_a_cyclic_automaton() -> None:
    """`ab` accepts exactly one word, and its automaton still has a cycle.

    Not a defect, and worth writing down because it is the opposite of what the
    shape of the language suggests. Completeness requires a transition for every
    letter from every state, so the automaton carries a sink -- the empty
    language, whose every derivative is itself -- and the sink loops. So
    `has_cycles()` on a derivative automaton is a statement about the automaton
    being complete, not about the language being infinite, and the grounded
    hyperset is non-well-founded for the same reason.
    """
    apg = dfa_apg(A.concat(B), alphabet=ALPHA, max_states=16)
    assert apg.has_cycles()
    sinks = [n for n in apg.nodes if apg.children(n) == {n}]
    assert len(sinks) == 1, [str(n) for n in apg.nodes]
    assert str(sinks[0].label) == str(Regex.empty())
