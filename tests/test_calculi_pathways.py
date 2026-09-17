"""Tests for meta-features, language calculus, meta-calculus, hyper-calculus, and math calculus."""

from __future__ import annotations


from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node
from grounded_hyperset_theory.hyper_calculus import (
    all_orbits,
    automorphism_group,
    orbit,
    quotient_by_symmetry,
    symmetry_group_order,
)
from grounded_hyperset_theory.hyperset import (
    Hyperset,
    QuineAtom,
    bisimilar,
    von_neumann_ordinal,
)
from grounded_hyperset_theory.language_calculus import (
    Alphabet,
    Grammar,
    ProductionRule,
    Symbol,
    SyntaxTree,
    Word,
    derivation_step,
    quote_syntax,
    unquote_syntax,
)
from grounded_hyperset_theory.math_calculus import (
    CauchySequenceHyperset,
    DedekindCutHyperset,
    hyperset_derivative_sequence,
    hyperset_integer,
    hyperset_rational,
    hyperset_to_integer,
    hyperset_to_rational,
    rational_add,
    rational_lt,
    rational_mul,
    surreal_infinitesimal,
    surreal_minus_one,
    surreal_omega,
    surreal_one,
    surreal_zero,
)
from grounded_hyperset_theory.meta import (
    Abstraction,
    abstract,
    deobjectify_apg,
    deobjectify_function,
    deobjectify_relation,
    fractal_hyperset,
    meta_fractalize,
    objectify_apg,
    objectify_function,
    objectify_relation,
    unfold_step,
)
from grounded_hyperset_theory.meta_calculus import (
    RewriteRule,
    RewriteTrajectory,
    RewritingSystem,
    trajectory_bisimilar,
    trajectory_quotient,
)


# ==========================================
# 1. Meta-features: Abstraction & Objectification
# ==========================================

def test_abstraction_and_instantiation():
    # Construct body: { x, ∅ }
    x_node = Node("x")
    empty_node = Node("empty")
    root = Node("root")
    edges = {root: [x_node, empty_node], x_node: [], empty_node: []}
    body = Hyperset(AccessiblePointedGraph(root=root, edges=edges))

    abs_x = Abstraction(variable=x_node, body=body)

    # Instantiate with 1 = {∅}
    one = von_neumann_ordinal(1)
    instantiated = abs_x.instantiate(one)

    # Result should be { {∅}, ∅ } = 2
    two = von_neumann_ordinal(2)
    assert instantiated == two
    assert von_neumann_ordinal(0) in instantiated
    assert one in instantiated


def test_abstract_factory_and_to_hyperset():
    two = von_neumann_ordinal(2)  # {0, 1}
    # Abstract over 0
    zero = von_neumann_ordinal(0)
    # Target hyperset has members 0 and 1
    abs_obj = abstract(two, parameter=zero.apg.root, var_name="param_z")
    assert abs_obj.variable.id == "param_z"

    # Re-instantiate with zero gives two back
    recovered = abs_obj.instantiate(zero)
    assert recovered == two

    # Reify abstraction as a first-class hyperset
    h_abs = abs_obj.to_hyperset()
    assert isinstance(h_abs, Hyperset)
    assert not h_abs.is_empty


def test_objectify_and_deobjectify_relation():
    zero = von_neumann_ordinal(0)
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)

    pairs = [(zero, one), (one, two)]
    rel_h = objectify_relation(pairs)
    assert len(rel_h) == 2

    recovered_pairs = deobjectify_relation(rel_h)
    assert len(recovered_pairs) == 2
    assert (zero, one) in recovered_pairs
    assert (one, two) in recovered_pairs


def test_objectify_and_deobjectify_function():
    zero = von_neumann_ordinal(0)
    one = von_neumann_ordinal(1)
    two = von_neumann_ordinal(2)

    fn_map = {zero: one, one: two}
    fn_h = objectify_function(fn_map)
    recovered_map = deobjectify_function(fn_h)
    assert recovered_map == fn_map


def test_objectify_and_deobjectify_apg():
    omega = QuineAtom()
    apg_h = objectify_apg(omega.apg)
    recovered_apg = deobjectify_apg(apg_h)
    assert bisimilar(omega.apg, recovered_apg)


def test_fractal_hypersets_and_unfold():
    # Quine nested: Phi = {Phi, {Phi}}
    phi = fractal_hyperset("quine_nested")
    assert phi in phi  # Phi in Phi
    s_members = [m for m in phi.members() if m != phi]
    assert len(s_members) == 1
    assert phi in s_members[0]  # {Phi} contains Phi

    # Sierpinski 3-cycle
    sierpinski = fractal_hyperset("sierpinski")
    assert not sierpinski.is_well_founded
    assert len(sierpinski.members()) == 2

    # Cantor non-well-founded
    cantor = fractal_hyperset("cantor_non_well_founded")
    assert not cantor.is_well_founded

    # Unfold step preserves bisimulation
    unfolded = unfold_step(phi)
    assert unfolded == phi


def test_meta_fractalize():
    seed = von_neumann_ordinal(1)  # {0}
    def rule(h):
        return [h, Hyperset.from_elements(h)]

    fractal = meta_fractalize(seed, rule, depth=2)
    assert len(fractal.members()) > 1


# ==========================================
# 2. Language Calculus
# ==========================================

def test_language_symbols_alphabets_words():
    sym_a = Symbol("a", is_terminal=True)
    sym_b = Symbol("b", is_terminal=True)
    sym_s = Symbol("S", is_terminal=False)

    alpha = Alphabet([sym_a, sym_b, sym_s])
    assert "a" in alpha
    assert sym_b in alpha
    assert len(alpha) == 3

    word = Word.from_str("aba")
    assert len(word) == 3

    word_h = word.to_hyperset()
    assert isinstance(word_h, Hyperset)
    assert not word_h.is_empty


def test_grammar_and_syntax_tree():
    s = Symbol("S", is_terminal=False)
    a = Symbol("a", is_terminal=True)
    prod = ProductionRule(lhs=s, rhs=(a, s))

    grammar = Grammar(variables=[s], terminals=[a], productions=[prod], start=s)
    g_h = grammar.to_hyperset()
    assert isinstance(g_h, Hyperset)

    # Syntax tree S(a, S(a))
    leaf1 = SyntaxTree("a")
    leaf2 = SyntaxTree("a")
    sub = SyntaxTree("S", children=[leaf2])
    root = SyntaxTree("S", children=[leaf1, sub])

    st_h = root.to_hyperset()
    assert isinstance(st_h, Hyperset)
    assert st_h.is_well_founded

    # Derivation step
    step_trees = derivation_step(SyntaxTree("S"), prod)
    assert len(step_trees) >= 1
    assert step_trees[0].label == "S"
    assert len(step_trees[0].children) == 2


def test_quote_and_unquote_syntax():
    expr = (1, 2, (3, 4))
    q = quote_syntax(expr)
    assert isinstance(q, Hyperset)
    # Unquote returns reconstructed tuple structure
    unquoted = unquote_syntax(q)
    assert isinstance(unquoted, tuple)


# ==========================================
# 3. Meta-Calculus: Rewriting Dynamics & Bisimulation
# ==========================================

def test_rewriting_system_dynamics_and_confluence():
    # A simple rewrite system on ordinals: n+1 -> n
    rule_pred = RewriteRule(
        name="predecessor",
        transform=lambda h: [von_neumann_ordinal(h.to_int() - 1)] if h.is_well_founded and h.to_int() > 0 else [],
    )
    system = RewritingSystem([rule_pred])

    three = von_neumann_ordinal(3)
    apg = system.reduction_apg(three, max_depth=5)
    assert len(apg.nodes) == 4  # 3, 2, 1, 0

    assert system.is_confluent(three)
    attractors = system.find_attractors(three)
    assert len(attractors) == 1
    assert attractors[0].is_empty  # reaches 0


def test_trajectory_bisimulation():
    # Trajectory 1: 0 -> 1 -> 2
    t1 = RewriteTrajectory((von_neumann_ordinal(0), von_neumann_ordinal(1), von_neumann_ordinal(2)))
    # Trajectory 2: 0 -> 1 -> 2 (same structure)
    t2 = RewriteTrajectory((von_neumann_ordinal(0), von_neumann_ordinal(1), von_neumann_ordinal(2)))
    assert trajectory_bisimilar(t1, t2)

    # Trajectory with cycle: 0 -> 1 -> 0
    t_cycle = RewriteTrajectory((von_neumann_ordinal(0), von_neumann_ordinal(1), von_neumann_ordinal(0)))
    apg_quotient = trajectory_quotient(t_cycle)
    assert apg_quotient.has_cycles()


# ==========================================
# 4. Hyper-Calculus: Symmetries & Automorphisms
# ==========================================

def test_apg_automorphism_and_symmetries():
    # Graph with symmetry: root points to a and b, both are leaves
    root = Node("r")
    a = Node("a")
    b = Node("b")
    apg = AccessiblePointedGraph(root=root, edges={root: [a, b], a: [], b: []})

    group = automorphism_group(apg)
    # Must have 2 automorphisms: identity and swap(a, b)
    assert len(group) == 2

    id_aut = next(g for g in group if g(a) == a)
    swap_aut = next(g for g in group if g(a) == b)

    assert swap_aut(b) == a
    assert swap_aut(root) == root

    # Group axioms
    # Inverse of swap is swap
    assert (swap_aut * swap_aut) == id_aut
    assert swap_aut.inverse() == swap_aut

    # Orbits
    orb_a = orbit(a, group)
    assert orb_a == {a, b}

    orbits = all_orbits(apg, group)
    assert len(orbits) == 2  # {r} and {a, b}

    # Symmetry quotient collapses a and b
    sym_quotient = quotient_by_symmetry(apg, group)
    assert len(sym_quotient.nodes) == 2


def test_hyperset_symmetry_queries():
    # {1, 2} has non-trivial symmetry if represented symmetrically
    h = Hyperset.from_elements(von_neumann_ordinal(1), von_neumann_ordinal(2))
    assert symmetry_group_order(h) >= 1


# ==========================================
# 5. Math Calculus: Dedekind Cuts, Cauchy Sequences, Surreals
# ==========================================

def test_hyperset_integers_and_rationals():
    # Integers
    pos5 = hyperset_integer(5)
    assert hyperset_to_integer(pos5) == 5

    neg3 = hyperset_integer(-3)
    assert hyperset_to_integer(neg3) == -3

    # Rationals
    half = hyperset_rational(1, 2)
    assert hyperset_to_rational(half) == (1, 2)

    two_thirds = hyperset_rational(2, 3)
    assert hyperset_to_rational(two_thirds) == (2, 3)

    # Arithmetic
    seven_sixths = rational_add(half, two_thirds)
    assert hyperset_to_rational(seven_sixths) == (7, 6)

    one_third = rational_mul(half, two_thirds)
    assert hyperset_to_rational(one_third) == (1, 3)

    assert rational_lt(half, two_thirds)


def test_cauchy_sequence():
    # Sequence converging to 1: q_n = 1 - 1/(n+1) = n/(n+1)
    seq = CauchySequenceHyperset(lambda n: (n, n + 1))
    assert seq.term(0) == (0, 1)
    assert seq.term(1) == (1, 2)
    assert seq.term(9) == (9, 10)

    # Modulus for 1/k convergence: n_k = k
    assert seq.is_cauchy(lambda k: k, samples=5)

    # Reify sequence as hyperset
    seq_h = seq.to_hyperset(length=4)
    assert isinstance(seq_h, Hyperset)
    assert len(seq_h) == 4


def test_dedekind_cuts():
    # Rational cut for 1/2
    cut_half = DedekindCutHyperset.from_rational(1, 2)
    assert cut_half.contains_rational(1, 3)
    assert not cut_half.contains_rational(2, 3)

    # Cut for sqrt(2)
    sqrt2_cut = DedekindCutHyperset.sqrt2()
    assert sqrt2_cut.contains_rational(1, 1)      # 1 < sqrt(2)
    assert sqrt2_cut.contains_rational(7, 5)      # 1.4 < sqrt(2)
    assert not sqrt2_cut.contains_rational(3, 2)  # 1.5 > sqrt(2)
    assert not sqrt2_cut.contains_rational(1415, 1000)

    # Reify cut to hyperset
    cut_h = sqrt2_cut.to_hyperset()
    assert isinstance(cut_h, Hyperset)


def test_surreal_numbers_and_infinitesimals():
    zero = surreal_zero()
    one = surreal_one()
    minus_one = surreal_minus_one()

    assert zero.is_zero()
    assert not one.is_zero()

    assert minus_one < zero
    assert zero < one

    eps = surreal_infinitesimal(depth=3)
    assert eps.is_infinitesimal()
    assert not eps.is_zero()
    assert zero < eps

    om = surreal_omega(depth=3)
    assert om.is_infinite()
    assert one < om

    # Hyperset reification
    eps_h = eps.to_hyperset()
    assert isinstance(eps_h, Hyperset)


def test_hyperset_derivative_sequence():
    # Function f(x) = x^2, derivative at x = 2 should be 4
    # (x+h)^2 - x^2 = 2xh + h^2 => difference quotient = 2x + h = 4 + h
    def f_sq(r: tuple[int, int]) -> tuple[int, int]:
        p, q = r
        return (p * p, q * q)

    diff_seq = hyperset_derivative_sequence(f_sq, x=(2, 1))
    # For h = 1/2, 4 + 1/2 = 9/2
    assert diff_seq.term(0) == (9, 2)
    # For h = 1/4, 4 + 1/4 = 17/4
    assert diff_seq.term(1) == (17, 4)
    # For h = 1/8, 4 + 1/8 = 33/8
    assert diff_seq.term(2) == (33, 8)
