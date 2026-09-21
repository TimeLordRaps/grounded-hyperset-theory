"""Regression tests for Hypersets, bisimulation, and constructive membership."""

from __future__ import annotations

from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node
from grounded_hyperset_theory.hyperset import (
    EmptyHyperset,
    Hyperset,
    QuineAtom,
    bisimilar,
    pair,
    von_neumann_ordinal,
)



def test_empty_set():
    empty = EmptyHyperset()
    assert empty.is_well_founded
    assert len(empty.members()) == 0
    assert empty not in empty


def test_quine_atom_self_membership():
    omega = QuineAtom()
    assert not omega.is_well_founded
    # Crucial property of Quine atom: Ω ∈ Ω
    assert omega.contains(omega)
    assert omega in omega


def test_quine_atom_bisimulation_collapse():
    """Theorem of Aczel's AFA: A 2-cycle a = {b}, b = {a} is bisimilar to the 1-cycle Ω = {Ω}."""
    # 1-cycle: 0 -> 0
    omega1 = QuineAtom()

    # 2-cycle: a -> b -> a
    a = Node("a")
    b = Node("b")
    apg_2cycle = AccessiblePointedGraph(root=a, edges={a: [b], b: [a]})
    omega2 = Hyperset(apg_2cycle)

    assert omega2 in omega2
    # Under AFA, they denote the exact same unique hyperset
    assert bisimilar(omega1.apg, omega2.apg)
    assert omega1 == omega2


def test_finite_ordinals():
    # Von Neumann ordinals:
    # 0 = ∅
    zero = EmptyHyperset()

    # 1 = {0}
    one_node = Node(1)
    zero_node = Node(0)
    one = Hyperset(root=one_node, edges={one_node: [zero_node], zero_node: []})

    assert zero in one
    assert one not in zero
    assert one.is_well_founded


def test_from_elements_and_cardinality():
    zero = EmptyHyperset()
    one = Hyperset.from_elements(zero)
    assert len(one) == 1
    assert zero in one

    # Set with duplicate representation of zero
    zero_alt = Hyperset(root="z", edges={"z": []})
    two_with_dups = Hyperset.from_elements(zero, zero_alt)
    # Cardinality modulo bisimulation must collapse {0, 0'} to 1 element
    assert two_with_dups.cardinality() == 1
    assert len(two_with_dups) == 1
    assert two_with_dups == one


def test_set_operations_union_intersection_difference():
    zero = EmptyHyperset()
    one = Hyperset.from_elements(zero)
    two = Hyperset.from_elements(zero, one)

    # Union
    u = one | two
    assert u == two
    assert zero in u
    assert one in u

    # Intersection
    inter = one & two
    assert inter == one
    assert zero in inter
    assert one not in inter

    # Disjoint intersection
    empty = EmptyHyperset()
    assert (empty & one) == empty

    # Difference
    diff = two - one
    assert diff == Hyperset.from_elements(one)
    assert one in diff
    assert zero not in diff

    assert (one - one) == empty


def test_subset_relations():
    zero = EmptyHyperset()
    one = Hyperset.from_elements(zero)
    two = Hyperset.from_elements(zero, one)

    assert zero.is_empty
    assert not one.is_empty

    # Subsets
    assert zero <= one
    assert zero < one
    assert one <= two
    assert one < two
    assert not (two <= one)
    assert not (two < one)

    # Reflexivity
    assert one <= one
    assert not (one < one)

    # Supersets
    assert two >= one
    assert two > one
    assert not (one >= two)


def test_von_neumann_ordinals_construction_and_theorems():
    from grounded_hyperset_theory.hyperset import von_neumann_ordinal

    ordinals = [von_neumann_ordinal(i) for i in range(5)]

    for i, ord_i in enumerate(ordinals):
        assert ord_i.is_well_founded
        assert ord_i.is_transitive()
        assert ord_i.is_ordinal()
        assert ord_i.cardinality() == i
        assert len(ord_i) == i

        # Every preceding ordinal is constructively a member and a proper subset
        for j in range(i):
            ord_j = ordinals[j]
            assert ord_j in ord_i
            assert ord_j < ord_i
            assert ord_j <= ord_i

        # Non-membership for >=
        for j in range(i, len(ordinals)):
            ord_j = ordinals[j]
            assert ord_j not in ord_i


def test_non_ordinal_and_transitivity_failure():
    zero = EmptyHyperset()
    one = Hyperset.from_elements(zero)
    # S = {{0}}
    # Member is {0} (one). But 0 is not a member of S, so {0} is not a subset of S!
    s = Hyperset.from_elements(one)
    assert s.is_well_founded
    assert not s.is_transitive()
    assert not s.is_ordinal()


def test_kuratowski_pair():
    from grounded_hyperset_theory.hyperset import pair, von_neumann_ordinal

    zero = von_neumann_ordinal(0)
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)

    p1 = pair(zero, one)
    p2 = pair(zero, one)
    p3 = pair(one, zero)
    p4 = pair(zero, two)

    # (a, b) = (c, d) iff a = c and b = d
    assert p1 == p2
    assert p1 != p3
    assert p1 != p4

    # Pair with non-well-founded Quine atom
    omega = QuineAtom()
    p_omega = pair(omega, zero)
    assert pair(omega, zero) == p_omega


def test_aczel_solution_lemma_systems():
    from grounded_hyperset_theory.hyperset import solve_system

    # System 1: x = {x} -> Quine atom
    s1 = solve_system({"x": ["x"]})
    omega = QuineAtom()
    assert s1["x"] == omega
    assert s1["x"] in s1["x"]

    # System 2: x = {y}, y = {x} -> both equal to Quine atom
    s2 = solve_system({"x": ["y"], "y": ["x"]})
    assert s2["x"] == omega
    assert s2["y"] == omega
    assert s2["x"] == s2["y"]

    # System 3: 3-cycle x -> y -> z -> x -> all collapse to Quine atom
    s3 = solve_system({"x": ["y"], "y": ["z"], "z": ["x"]})
    assert s3["x"] == omega
    assert s3["y"] == omega
    assert s3["z"] == omega

    # System 4: mutual cycle with distinct constants
    # a = {b, 0}, b = {a, 1}
    s4 = solve_system({
        "a": ["b", "0"],
        "b": ["a", "1"],
        "0": [],
        "1": ["0"],
    })
    a = s4["a"]
    b = s4["b"]
    assert not a.is_well_founded
    assert not b.is_well_founded
    assert b in a
    assert a in b
    assert s4["0"] in a
    assert s4["1"] in b

    # System 5: Aczel's Parameterized Solution Lemma with embedded Hyperset constants
    # x = {x, 1}
    one = von_neumann_ordinal(1)
    s5 = solve_system({"x": ["x", one]})
    x = s5["x"]
    assert not x.is_well_founded
    assert x in x
    assert one in x
    assert von_neumann_ordinal(0) not in x
    assert len(x) == 2
    assert bisimilar(x.apg, x.apg)

    # System 6: Multiple variables with mixed QuineAtom and ordinal constants
    # p = {q, Ω}, q = {p, 2}
    two = von_neumann_ordinal(2)
    s6 = solve_system({
        "p": ["q", omega],
        "q": ["p", two],
    })
    p = s6["p"]
    q = s6["q"]
    assert not p.is_well_founded
    assert not q.is_well_founded
    assert q in p
    assert omega in p
    assert p in q
    assert two in q
    assert len(p) == 2
    assert len(q) == 2



def test_non_well_founded_set_operations():
    omega = QuineAtom()
    zero = EmptyHyperset()

    # Union of Quine atom with 0: Ω ∪ {0} = {Ω, 0}
    s = omega | Hyperset.from_elements(zero)
    assert not s.is_well_founded
    assert omega in s
    assert zero in s
    assert s.cardinality() == 2

    # Intersection of Quine atom with empty set
    assert (omega & zero) == zero

    # Difference
    assert (omega - Hyperset.from_elements(omega)) == zero
    assert (omega - Hyperset.from_elements(zero)) == omega


def test_canonical_bisimulation_quotient():
    # 2-cycle a -> b -> a
    a = Node("a")
    b = Node("b")
    omega_2cycle = Hyperset(AccessiblePointedGraph(root=a, edges={a: [b], b: [a]}))
    assert len(omega_2cycle.apg.nodes) == 2

    canonical_omega = omega_2cycle.canonical()
    # Quotient graph must have exactly 1 node
    assert len(canonical_omega.apg.nodes) == 1
    assert canonical_omega == QuineAtom()


def test_type_and_value_errors():
    import pytest
    from grounded_hyperset_theory.hyperset import pair, von_neumann_ordinal

    empty = EmptyHyperset()
    with pytest.raises(TypeError):
        von_neumann_ordinal("not_an_int")
    with pytest.raises(TypeError):
        von_neumann_ordinal(True)
    with pytest.raises(ValueError):
        von_neumann_ordinal(-1)

    with pytest.raises(TypeError):
        empty.union(42)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        empty.intersection("string")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        empty.difference(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        empty.is_subset([1, 2])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        empty.is_proper_subset(0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        empty.is_superset(1.5)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        pair(empty, "not_a_hyperset")  # type: ignore[arg-type]


def test_powerset():
    empty = EmptyHyperset()
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)

    # P(∅) = {∅} = 1
    p_empty = empty.powerset()
    assert len(p_empty) == 1
    assert empty in p_empty
    assert p_empty == one

    # P(1) = {∅, {∅}} = {0, 1} = 2
    p_one = one.powerset()
    assert len(p_one) == 2
    assert empty in p_one
    assert one in p_one
    assert p_one == two

    # P(2) has 2^2 = 4 subsets
    p_two = two.powerset()
    assert len(p_two) == 4
    assert empty in p_two
    assert one in p_two
    assert two in p_two

    # P(Ω) = {∅, Ω} (subsets of Quine atom are ∅ and Ω)
    omega = QuineAtom()
    p_omega = omega.powerset()
    assert len(p_omega) == 2
    assert empty in p_omega
    assert omega in p_omega


def test_big_union_and_big_intersection():
    import pytest
    empty = EmptyHyperset()
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)
    three = von_neumann_ordinal(3)
    omega = QuineAtom()

    # ⋃ ∅ = ∅
    assert empty.big_union() == empty
    # ⋃ 1 = ⋃ {0} = 0 = ∅
    assert one.big_union() == empty
    # ⋃ 2 = ⋃ {0, 1} = 1
    assert two.big_union() == one
    # ⋃ 3 = 2
    assert three.big_union() == two
    # ⋃ Ω = Ω (Quine atom is self-union)
    assert omega.big_union() == omega

    # ⋂ ∅ is undefined in standard set theory
    with pytest.raises(ValueError, match="undefined"):
        empty.big_intersection()

    # ⋂ { {0, 1}, {1, 2} } = {1}
    set_a = Hyperset.from_elements(empty, one)
    set_b = Hyperset.from_elements(one, two)
    family = Hyperset.from_elements(set_a, set_b)
    assert family.big_intersection() == Hyperset.from_elements(one)

    # ⋂ Ω = Ω
    assert omega.big_intersection() == omega


def test_cartesian_product():
    empty = EmptyHyperset()
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)

    # ∅ × 2 = ∅
    assert empty.cartesian_product(two) == empty
    assert two.cartesian_product(empty) == empty

    # 2 × 2 has 4 Kuratowski pairs
    prod = two.cartesian_product(two)
    assert len(prod) == 4
    for a in [empty, one]:
        for b in [empty, one]:
            assert pair(a, b) in prod


def test_transitive_closure():
    empty = EmptyHyperset()
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)
    omega = QuineAtom()

    # TC(∅) = ∅
    assert empty.transitive_closure() == empty
    # TC(1) = 1 (already transitive)
    assert one.transitive_closure() == one
    # S = {{0}} -> not transitive. TC(S) = {0, {0}} = 2
    non_trans = Hyperset.from_elements(one)
    assert not non_trans.is_transitive()
    tc = non_trans.transitive_closure()
    assert tc.is_transitive()
    assert tc == two

    # TC(Ω) = Ω
    assert omega.transitive_closure() == omega


def test_ordinal_arithmetic_and_int_conversion():
    import pytest
    from grounded_hyperset_theory.hyperset import ordinal_add, ordinal_mul, ordinal_pow

    zero = von_neumann_ordinal(0)
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)
    three = von_neumann_ordinal(3)

    assert int(zero) == 0
    assert int(one) == 1
    assert int(two) == 2
    assert int(three) == 3

    # Addition
    assert ordinal_add(two, three) == von_neumann_ordinal(5)
    assert ordinal_add(zero, two) == two
    assert ordinal_add(two, zero) == two

    # Multiplication
    assert ordinal_mul(two, three) == von_neumann_ordinal(6)
    assert ordinal_mul(zero, three) == zero
    assert ordinal_mul(one, three) == three

    # Exponentiation
    assert ordinal_pow(two, 3) == von_neumann_ordinal(8)
    assert ordinal_pow(two, three) == von_neumann_ordinal(8)
    assert ordinal_pow(two, 0) == one
    assert ordinal_pow(zero, 0) == one
    assert ordinal_pow(zero, 5) == zero

    # Errors on non-ordinal or non-well-founded
    omega = QuineAtom()
    with pytest.raises(ValueError, match="non-well-founded"):
        omega.to_int()

    non_ord = Hyperset.from_elements(one)
    with pytest.raises(ValueError, match="not a von Neumann ordinal"):
        non_ord.to_int()


def test_hyperset_hashability_and_set_operations():
    omega1 = QuineAtom()
    # 2-cycle bisimilar to Quine atom
    a, b = Node("a"), Node("b")
    omega2 = Hyperset(AccessiblePointedGraph(root=a, edges={a: [b], b: [a]}))

    assert hash(omega1) == hash(omega2)
    s = {omega1, omega2}
    assert len(s) == 1
    assert omega1 in s
    assert omega2 in s

    zero = EmptyHyperset()
    mapping = {zero: "zero", omega1: "omega"}
    assert mapping[von_neumann_ordinal(0)] == "zero"
    assert mapping[omega2] == "omega"
