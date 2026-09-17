"""Deep regression tests for meta-features, calculi bridges, bisimulation under Aczel's AFA, and cycle preservation."""

from __future__ import annotations

import pytest

from grounded_hyperset_theory.abstraction import (
    NodePartition,
    depth_abstract_hyperset,
    depth_abstraction,
    is_bisimulation_congruence,
    is_congruence,
    predicate_abstraction,
    quotient_apg,
    refine_to_bisimulation,
    scc_abstract_hyperset,
    scc_quotient,
)
from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node
from grounded_hyperset_theory.hyper_calculus import (
    Permutation,
    cyclic_group,
    discrete_derivative,
    find_apg_automorphisms,
    is_invariant_under,
    orbit_quotient_apg,
)
from grounded_hyperset_theory.hyperset import (
    Hyperset,
    QuineAtom,
    bisimilar,
    von_neumann_ordinal,
)
from grounded_hyperset_theory.language_calculus import (
    Grammar,
    ProductionRule,
    Regex,
    Symbol,
    dfa_apg,
    dfa_hyperset,
    grammar_bisimilar,
    liar_sentence,
    self_referential_term,
    syntax_bisimilar,
)
from grounded_hyperset_theory.meta_calculus import (
    RewriteRule,
    RewriteTrajectory,
    RewritingSystem,
    create_hyperset_rewrite_system,
    find_periodic_orbits,
    is_locally_confluent,
    is_terminating,
    normal_forms,
    trajectory_bisimilar,
    trajectory_hyperset,
)
from grounded_hyperset_theory.real_analysis_bridge import (
    CauchySequence,
    DedekindCut,
    GroundedInteger,
    GroundedRational,
    SurrealNumber,
    derivative_quotient,
    riemann_integral,
    symbolic_polynomial_derivative,
    symbolic_polynomial_integral,
)


# =========================================================================
# 1. Abstraction, Partitioning, Congruences, and SCC Condensation
# =========================================================================

def test_node_partition_construction_and_refine():
    n0, n1, n2, n3 = Node(0), Node(1), Node(2), Node(3)
    p1 = NodePartition.from_blocks([[n0, n1], [n2, n3]])
    assert p1.is_equivalent(n0, n1)
    assert not p1.is_equivalent(n0, n2)
    assert len(p1.blocks()) == 2

    # Equivalence relation constructor
    p_mod2 = NodePartition.from_relation([n0, n1, n2, n3], lambda u, v: (u.id % 2) == (v.id % 2))
    assert p_mod2.is_equivalent(n0, n2)
    assert p_mod2.is_equivalent(n1, n3)
    assert not p_mod2.is_equivalent(n0, n1)

    # Refine (meet of partitions)
    refined = p1.refine(p_mod2)
    assert len(refined.blocks()) == 4
    for u in [n0, n1, n2, n3]:
        for v in [n0, n1, n2, n3]:
            if u != v:
                assert not refined.is_equivalent(u, v)


def test_congruence_and_bisimulation_partition():
    # 2-cycle a -> b -> a
    a, b = Node("a"), Node("b")
    apg_2cycle = AccessiblePointedGraph(root=a, edges={a: [b], b: [a]})

    # Partition merging a and b into block 0
    part = NodePartition.from_mapping({a: 0, b: 0})
    assert is_congruence(apg_2cycle, part)
    assert is_bisimulation_congruence(apg_2cycle, part)

    # Refine to coarsest bisimulation partition
    coarsest = refine_to_bisimulation(apg_2cycle)
    assert len(coarsest.blocks()) == 1
    assert coarsest.is_equivalent(a, b)

    # Quotient collapses to 1-cycle
    q_apg = quotient_apg(apg_2cycle, part)
    assert len(q_apg.nodes) == 1
    assert q_apg.children(q_apg.root) == {q_apg.root}
    assert bisimilar(q_apg, QuineAtom().apg)


def test_depth_abstraction_and_truncation():
    # Linear chain: 0 -> 1 -> 2 -> 3 -> 4
    edges = {Node(i): [Node(i + 1)] for i in range(4)}
    edges[Node(4)] = []
    chain_apg = AccessiblePointedGraph(root=Node(0), edges=edges)

    # Depth abstraction with max_depth = 2
    d2 = depth_abstraction(chain_apg, max_depth=2)
    # Root at depth 0, child at depth 1, horizon at depth 2
    assert len(d2.nodes) <= 3
    assert not d2.has_cycles()

    # Hyperset level
    h_chain = Hyperset(chain_apg)
    h_d2 = depth_abstract_hyperset(h_chain, max_depth=2)
    assert isinstance(h_d2, Hyperset)


def test_predicate_abstraction():
    # Nodes with and without self-loops
    n0, n1, n2 = Node(0), Node(1), Node(2)
    apg = AccessiblePointedGraph(root=n0, edges={n0: [n1, n2], n1: [n1], n2: []})

    def has_self_loop(n):
        return n in apg.children(n)
    def is_leaf(n):
        return len(apg.children(n)) == 0

    pred_apg = predicate_abstraction(apg, [has_self_loop, is_leaf])
    assert len(pred_apg.nodes) <= 3


def test_scc_quotient_condensation_dag():
    # Non-well-founded cyclic graph: 3-cycle 1 -> 2 -> 3 -> 1, with exit to 4 -> 4
    n1, n2, n3, n4 = Node(1), Node(2), Node(3), Node(4)
    edges = {
        n1: [n2],
        n2: [n3],
        n3: [n1, n4],
        n4: [n4],
    }
    apg = AccessiblePointedGraph(root=n1, edges=edges)
    assert apg.has_cycles()

    # SCC condensation quotient contracts cycles to acyclic DAG
    dag = scc_quotient(apg)
    assert not dag.has_cycles()
    assert len(dag.nodes) == 2  # SCC {1,2,3} and SCC {4}

    # Hyperset level
    h_cyclic = Hyperset(apg)
    assert not h_cyclic.is_well_founded
    h_dag = scc_abstract_hyperset(h_cyclic)
    assert h_dag.is_well_founded


# =========================================================================
# 2. Meta-Calculus: Symbolic Dynamics & Confluence
# =========================================================================

def test_meta_calculus_branching_and_confluence():
    # State is an integer. Rewrite rules: x -> x // 2 if x > 0, x -> x - 1 if x > 0
    r_div = RewriteRule(
        name="half",
        transform=lambda h: [von_neumann_ordinal(h.to_int() // 2)] if h.is_well_founded and h.to_int() > 0 else [],
    )
    r_dec = RewriteRule(
        name="dec",
        transform=lambda h: [von_neumann_ordinal(h.to_int() - 1)] if h.is_well_founded and h.to_int() > 0 else [],
    )
    sys = RewritingSystem([r_div, r_dec])

    four = von_neumann_ordinal(4)
    traj_apg = sys.reduction_apg(four, max_depth=5)
    assert not traj_apg.has_cycles()
    assert is_terminating(traj_apg)
    assert is_locally_confluent(traj_apg)

    nf = normal_forms(traj_apg)
    assert len(nf) == 1
    # Terminal normal form is 0
    zero_node = next(iter(nf))
    assert traj_apg.children(zero_node) == set()


def test_meta_calculus_periodic_orbits_and_attractors():
    # Oscillating rewrite system: odd n -> n + 1, even n -> n - 1
    r_toggle = RewriteRule(
        name="toggle",
        transform=lambda h: [von_neumann_ordinal(2 if h.to_int() == 1 else 1)] if h.is_well_founded else [],
    )
    sys = RewritingSystem([r_toggle])
    one = von_neumann_ordinal(1)
    traj_apg = sys.reduction_apg(one, max_depth=6)

    assert traj_apg.has_cycles()
    assert not is_terminating(traj_apg)

    orbits = find_periodic_orbits(traj_apg)
    assert len(orbits) >= 1
    assert len(orbits[0]) == 2


def test_trajectory_hyperset_wrapping_and_bisimulation():
    zero = von_neumann_ordinal(0)
    one = von_neumann_ordinal(1)

    t1 = RewriteTrajectory((zero, one, zero))
    t2 = RewriteTrajectory((zero, one, zero))
    assert trajectory_bisimilar(t1, t2)

    h_traj = trajectory_hyperset(one, create_hyperset_rewrite_system(), max_states=10)
    assert isinstance(h_traj, Hyperset)


# =========================================================================
# 3. Hyper-Calculus: Groups, Permutations, and Automorphisms
# =========================================================================

def test_permutation_group_axioms_and_cycles():
    n0, n1, n2 = Node(0), Node(1), Node(2)
    # Cycle (0 -> 1 -> 2 -> 0)
    p_cyc = Permutation.from_cycle([n0, n1, n2], [n0, n1, n2])
    assert p_cyc.order() == 3
    assert p_cyc.apply(n0) == n1
    assert p_cyc.apply(n1) == n2
    assert p_cyc.apply(n2) == n0

    p_inv = p_cyc.inverse()
    assert (p_cyc * p_inv).is_identity
    assert (p_inv * p_cyc).is_identity

    # Group generated by 3-cycle
    g = cyclic_group([n0, n1, n2])
    assert g.order == 3
    assert g.is_abelian()

    orbits = g.orbits([n0, n1, n2])
    assert len(orbits) == 1
    assert orbits[0] == {n0, n1, n2}


def test_apg_automorphism_and_group():
    # Symmetric diamond graph: root points to a and b; both point to leaf c
    r, a, b, c = Node("r"), Node("a"), Node("b"), Node("c")
    edges = {r: [a, b], a: [c], b: [c], c: []}
    apg = AccessiblePointedGraph(root=r, edges=edges)

    aut_group = find_apg_automorphisms(apg, pointed=True)
    assert aut_group.order == 2  # Identity and swap(a, b)

    # Orbit quotient collapses a and b
    q_apg = orbit_quotient_apg(apg, aut_group)
    assert len(q_apg.nodes) == 3  # r, [a, b], c

    h_sym = Hyperset(apg)
    assert is_invariant_under(h_sym, aut_group)


def test_hyper_calculus_discrete_derivative():
    # If a hyperset is invariant under a swap symmetry, its discrete derivative is empty
    r, a, b = Node("r"), Node("a"), Node("b")
    apg = AccessiblePointedGraph(root=r, edges={r: [a, b], a: [], b: []})
    h = Hyperset(apg)

    swap = Permutation.from_mapping({r: r, a: b, b: a})
    d_swap = discrete_derivative(h, swap)
    assert d_swap.is_empty  # Symmetric difference is empty!


# =========================================================================
# 4. Language Calculus: Quotation Trees, Circular Syntax, and DFAs
# =========================================================================

def test_circular_syntax_and_liar_bisimulation():
    # Liar sentence L1: L1 = not(L1)
    l1 = liar_sentence()
    assert not l1.is_well_founded
    assert l1 in l1

    # 2-cycle Liar sentence L2: La = not(Lb), Lb = not(La)
    l2 = self_referential_term("La", {"La": ("not", ["Lb"]), "Lb": ("not", ["La"])})
    assert not l2.is_well_founded

    # Under Aczel's AFA, both circular syntax trees denote the exact same unique Liar concept!
    assert syntax_bisimilar(l1, l2)
    assert l1 == l2


def test_grammar_and_production_dependency_graph():
    s = Symbol("S", is_terminal=False)
    a = Symbol("a", is_terminal=True)
    p = ProductionRule(lhs=s, rhs=(a, s))
    g = Grammar(variables=[s], terminals=[a], productions=[p], start=s)

    assert g.is_recursive()
    apg = g.grammar_apg()
    assert apg.has_cycles()
    assert grammar_bisimilar(g, g)


def test_regex_brzozowski_derivatives_and_dfa():
    # Regex for (a | b)* . a
    reg_a = Regex.lit("a")
    reg_b = Regex.lit("b")
    reg_ab_star = reg_a.union(reg_b).star()
    reg = reg_ab_star.concat(reg_a)

    assert not reg.is_nullable
    # Derivative with respect to 'a' is nullable because 'a' matches
    da = reg.derivative("a")
    assert da.is_nullable

    # Build DFA state APG
    dfa = dfa_apg(reg, alphabet=["a", "b"], max_states=16)
    assert dfa.has_cycles()  # Kleene star loops create cycles!

    dfa_h = dfa_hyperset(reg, alphabet=["a", "b"], max_states=16)
    assert isinstance(dfa_h, Hyperset)
    assert not dfa_h.is_well_founded


# =========================================================================
# 5. Real Analysis Bridge: Exact Arithmetic, Dedekind Cuts, and Calculus
# =========================================================================

def test_grounded_integer_and_rational_arithmetic():
    i_pos = GroundedInteger(5)
    i_neg = GroundedInteger(-3)

    assert int(i_pos + i_neg) == 2
    assert int(i_pos * i_neg) == -15
    assert i_neg < i_pos

    h_pos = i_pos.to_hyperset()
    assert isinstance(h_pos, Hyperset)

    # Rationals
    q1 = GroundedRational(2, 3)
    q2 = GroundedRational(3, 4)

    assert q1 + q2 == GroundedRational(17, 12)
    assert q1 * q2 == GroundedRational(1, 2)
    assert q1 / q2 == GroundedRational(8, 9)
    assert q1 < q2

    # Reduction by gcd
    q_red = GroundedRational(10, 20)
    assert q_red.numerator == 1
    assert q_red.denominator == 2

    # Zero division error
    with pytest.raises(ZeroDivisionError):
        GroundedRational(1, 0)
    with pytest.raises(ZeroDivisionError):
        q1 / GroundedRational(0, 1)


def test_dedekind_cuts_bounding_and_approximation():
    sqrt2 = DedekindCut.sqrt_two()
    assert sqrt2.contains(GroundedRational(1, 1))
    assert sqrt2.contains(GroundedRational(14, 10))
    assert not sqrt2.contains(GroundedRational(15, 10))

    # Binary search bounding
    low, high = sqrt2.binary_search_interval(GroundedRational(1), GroundedRational(2), iterations=20)
    assert low.to_float() < 1.41421356 < high.to_float()

    approx = sqrt2.approximate(iterations=20)
    assert abs(approx - 1.41421356) < 1e-4

    # Golden ratio cut
    phi_cut = DedekindCut.golden_ratio()
    assert phi_cut.contains(GroundedRational(16, 10))
    assert not phi_cut.contains(GroundedRational(17, 10))


def test_cauchy_sequences_and_euler_e():
    seq_e = CauchySequence.euler_e()
    assert seq_e.is_cauchy(check_terms=10, epsilon=0.01)

    # Approximates e ~ 2.71828
    e_approx = seq_e.limit_approx(n=8)
    assert abs(e_approx - 2.71828) < 1e-3

    # Leibniz pi
    seq_pi = CauchySequence.pi_leibniz()
    pi_approx = seq_pi.limit_approx(n=20)
    assert abs(pi_approx - 3.14159) < 0.2


def test_surreal_numbers_and_infinitesimals():
    z = SurrealNumber.zero()
    one = SurrealNumber.one()
    minus_one = SurrealNumber.minus_one()
    half = SurrealNumber.half()
    eps = SurrealNumber.infinitesimal()

    assert z.to_float() == 0.0
    assert one.to_float() == 1.0
    assert minus_one.to_float() == -1.0
    assert half.to_float() == 0.5

    assert eps.is_infinitesimal()
    h_eps = eps.to_hyperset()
    assert isinstance(h_eps, Hyperset)


def test_calculus_differentiation_and_integration():
    # Classical derivative bridge: d/dx(x^3) at x = 2 is 3 * 2^2 = 12
    def f_cube(x):
        return x ** 3
    df = derivative_quotient(f_cube, 2.0)
    assert abs(df - 12.0) < 1e-4

    # Definite integral bridge: int_0^1 x^2 dx = 1/3
    def f_sq(x):
        return x ** 2
    integral = riemann_integral(f_sq, 0.0, 1.0, subdivisions=200)
    assert abs(integral - (1.0 / 3.0)) < 1e-3

    # Exact symbolic polynomial calculus: P(x) = 2 + 3x + 4x^2
    # P'(x) = 3 + 8x
    poly = [GroundedRational(2), GroundedRational(3), GroundedRational(4)]
    d_poly = symbolic_polynomial_derivative(poly)
    assert d_poly == [GroundedRational(3), GroundedRational(8)]

    # int P'(x) dx with C = 2 gives P(x) back
    int_poly = symbolic_polynomial_integral(d_poly, constant=GroundedRational(2))
    assert int_poly == poly
