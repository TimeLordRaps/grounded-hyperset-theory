"""Tests for the claims meta.py makes: abstraction, objectification, fractals.

Each section names a claim from a docstring and either pins it as true with a
case that could have failed, or pins the corrected statement with the
counterexample that forced the correction.

The module's one genuine defect was in ``unfold_step``, which is documented not
to change the bisimulation class and did. The trigger was node *names*: copies
were namespaced by interpolating two ids into one string, which is not injective
on pairs. ``test_the_collision`` and ``test_the_same_shape_under_other_names``
are the pair that proves it -- the same set, drawn with different node names,
got different answers.

Negative control: 4 of these 152 tests fail against the unfixed source and none
hang. That ratio is low on purpose and is not a weak control. Only
``unfold_step`` changed behaviour; every other correction in this module was to
a docstring that claimed more than the code did, so those tests pass against
both versions by design -- they exist to keep a corrected statement from drifting
back, not to detect the fix. The four that fail are exactly the four that put a
colliding pair of node names in front of ``unfold_step``, and all four failures
are wrong *sets*, not errors.

Two distinct collision modes show up there, and the second is the worse one:
``Node(12)`` and ``Node("12")`` are different nodes that ``str`` maps to the same
text, so no choice of separator would have saved it. Node ids are ``Hashable``,
not ``str``.
"""

from __future__ import annotations

import itertools

import pytest

from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node
from grounded_hyperset_theory.hyperset import (  # noqa: I001
    bisimilar,
    EmptyHyperset,
    Hyperset,
    QuineAtom,
    pair,
    von_neumann_ordinal,
)
from grounded_hyperset_theory.meta import (
    Abstraction,
    _unpack_pair,
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

PATTERNS = ["quine", "quine_nested", "sierpinski", "cantor_non_well_founded"]


def graph(edges: dict[str, list[str]], root: str) -> AccessiblePointedGraph:
    """Build an APG from a name -> children table."""
    nodes = {name: Node(name) for name in edges}
    return AccessiblePointedGraph(
        root=nodes[root],
        edges={nodes[a]: [nodes[b] for b in bs] for a, bs in edges.items()},
    )


def hyperset(edges: dict[str, list[str]], root: str) -> Hyperset:
    return Hyperset(graph(edges, root))


def relabel(edges: dict[str, list[str]], mapping: dict[str, str]) -> dict[str, list[str]]:
    """Rename every node, leaving the shape alone."""
    return {mapping[a]: [mapping[b] for b in bs] for a, bs in edges.items()}


# ==========================================================================
# 1. unfold_step does not change the set -- the defect and its control
# ==========================================================================

# root -> {a, a_b};  a -> {b};  b -> {z};  a_b -> {}
# The old namespacing built "copy_" + c.id + "_" + n.id, so the copy of the
# sibling a_b and the copy of b inside a were both called copy_a_b.
COLLIDING = {"r": ["a", "a_b"], "a": ["b"], "b": ["z"], "a_b": [], "z": []}
RENAMED = {"r": ["a", "W"], "a": ["b"], "b": ["z"], "W": [], "z": []}


def test_the_collision() -> None:
    """Two children whose names concatenate into one another's copy namespace."""
    h = hyperset(COLLIDING, "r")
    assert unfold_step(h) == h


def test_the_collision_preserves_member_sizes() -> None:
    """The empty sibling must stay empty. It used to acquire z."""
    h = hyperset(COLLIDING, "r")
    assert sorted(len(m) for m in unfold_step(h).members()) == [0, 1]


def test_the_same_shape_under_other_names() -> None:
    """The control: identical set, sibling renamed, and it always worked."""
    h = hyperset(RENAMED, "r")
    assert unfold_step(h) == h


def test_the_two_shapes_are_the_same_set() -> None:
    """Which is what makes the pair above a proof rather than two data points."""
    assert hyperset(COLLIDING, "r") == hyperset(RENAMED, "r")


@pytest.mark.parametrize(
    "sep",
    ["_", "", "-", "__"],
)
def test_names_that_concatenate_in_other_ways(sep: str) -> None:
    """Any separator is a guess about what ids contain. Tuples are not."""
    edges = {
        "r": ["x", f"x{sep}y"],
        "x": ["y"],
        "y": ["t"],
        f"x{sep}y": [],
        "t": [],
    }
    h = hyperset(edges, "r")
    assert unfold_step(h) == h


def test_integer_and_string_ids_that_collide_under_str() -> None:
    """Node ids are Hashable, not str. 12 and "12" are different nodes."""
    r, a, b = Node("r"), Node(12), Node("12")
    h = Hyperset(AccessiblePointedGraph(root=r, edges={r: [a, b], a: [Node("q")], b: [], Node("q"): []}))
    assert unfold_step(h) == h


@pytest.mark.parametrize(
    "name,edges,root",
    [
        ("empty", {"e": []}, "e"),
        ("singleton", {"r": ["e"], "e": []}, "r"),
        ("omega", {"w": ["w"]}, "w"),
        ("two-cycle", {"p": ["q"], "q": ["p"]}, "p"),
        ("shared child", {"r": ["a", "b"], "a": ["c"], "b": ["c"], "c": []}, "r"),
        ("diamond", {"r": ["a", "b"], "a": ["d"], "b": ["d"], "d": ["e"], "e": []}, "r"),
        ("self-loop child", {"r": ["s"], "s": ["s"]}, "r"),
        ("deep chain", {"r": ["a"], "a": ["b"], "b": ["c"], "c": ["d"], "d": []}, "r"),
    ],
)
def test_unfold_preserves_the_set(name: str, edges: dict[str, list[str]], root: str) -> None:
    h = hyperset(edges, root)
    assert unfold_step(h) == h, name


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4])
def test_unfold_preserves_ordinals(n: int) -> None:
    assert unfold_step(von_neumann_ordinal(n)) == von_neumann_ordinal(n)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_unfold_preserves_the_fractal_patterns(pattern: str) -> None:
    h = fractal_hyperset(pattern)
    assert unfold_step(h) == h


def test_unfold_is_invariant_under_renaming() -> None:
    """The result must not depend on what the nodes were called."""
    base = {"r": ["a", "b"], "a": ["c"], "b": ["c"], "c": []}
    names = ["r", "a", "b", "c"]
    for perm in itertools.permutations(["n0", "n1", "n2", "n3"]):
        mapping = dict(zip(names, perm))
        renamed = relabel(base, mapping)
        h = hyperset(renamed, mapping["r"])
        assert unfold_step(h) == h, mapping


def test_unfold_gives_each_child_a_private_copy() -> None:
    """The point of the function: siblings that shared structure no longer do."""
    h = hyperset({"r": ["a", "b"], "a": ["c"], "b": ["c"], "c": []}, "r")
    assert len(h.apg.nodes) == 4
    assert len(unfold_step(h).apg.nodes) > 4


# ==========================================================================
# 2. fractal_hyperset: four names, three sets
# ==========================================================================


def test_sierpinski_is_the_quine_atom() -> None:
    """A -> {B,C}, B -> {A,C}, C -> {A,B}: the all-pairs relation is a
    bisimulation, so the graph quotients to a single self-looping node."""
    assert fractal_hyperset("sierpinski") == QuineAtom()


def test_sierpinski_is_the_quine_pattern() -> None:
    assert fractal_hyperset("sierpinski") == fractal_hyperset("quine")


def test_sierpinski_has_one_member() -> None:
    assert len(fractal_hyperset("sierpinski")) == 1


def test_sierpinski_is_a_member_of_itself() -> None:
    s = fractal_hyperset("sierpinski")
    assert s in s


def test_the_four_patterns_denote_three_sets() -> None:
    sigs = {fractal_hyperset(p).canonical_signature() for p in PATTERNS}
    assert len(sigs) == 3


def test_quine_nested_is_genuinely_distinct() -> None:
    """Phi has a member not bisimilar to Phi, so it is not Omega."""
    phi = fractal_hyperset("quine_nested")
    assert phi != QuineAtom()
    assert phi in phi
    others = [m for m in phi.members() if m != phi]
    assert len(others) == 1
    assert phi in others[0]


def test_cantor_is_not_binary_branching() -> None:
    """{K, 0} and {0, K} are the same set, so the two branches are one."""
    k = fractal_hyperset("cantor_non_well_founded")
    assert len(k) == 1


def test_cantors_two_child_nodes_are_bisimilar() -> None:
    k = fractal_hyperset("cantor_non_well_founded")
    ms = k.members()
    assert len(ms) == 2
    assert ms[0] == ms[1]


def test_cantors_member_has_two_members() -> None:
    """K = {{K, 0}}: one member, and that member does have two."""
    k = fractal_hyperset("cantor_non_well_founded")
    inner = k.members()[0]
    assert len(inner) == 2
    assert k in inner
    assert EmptyHyperset() in inner


@pytest.mark.parametrize("pattern", PATTERNS)
def test_every_pattern_is_non_well_founded(pattern: str) -> None:
    assert not fractal_hyperset(pattern).is_well_founded


def test_an_unknown_pattern_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown fractal"):
        fractal_hyperset("menger")


# ==========================================================================
# 3. Abstraction: instantiate is right, to_hyperset is lossy
# ==========================================================================


def identity_abstraction() -> Abstraction:
    """lambda x. x, built the way `abstract` builds it."""
    return abstract(EmptyHyperset(), parameter=0, var_name="x")


def constant_abstraction() -> Abstraction:
    """lambda x. 0, where x does not occur."""
    return Abstraction(variable=Node("x"), body=EmptyHyperset())


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_the_identity_abstraction_is_the_identity(n: int) -> None:
    assert identity_abstraction()(von_neumann_ordinal(n)) == von_neumann_ordinal(n)


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_the_constant_abstraction_is_constant(n: int) -> None:
    assert constant_abstraction()(von_neumann_ordinal(n)) == EmptyHyperset()


def test_the_two_are_different_functions() -> None:
    two = von_neumann_ordinal(2)
    assert identity_abstraction()(two) != constant_abstraction()(two)


def test_but_they_objectify_to_the_same_hyperset() -> None:
    """The variable becomes a childless node, which is 0, so nothing records
    where it occurred -- and where it occurs is what an abstraction is."""
    assert identity_abstraction().to_hyperset() == constant_abstraction().to_hyperset()


def test_objectification_is_not_injective() -> None:
    """Stated as the general property, so a future encoding must break this."""
    a, b = identity_abstraction(), constant_abstraction()
    two = von_neumann_ordinal(2)
    assert a(two) != b(two) and a.to_hyperset() == b.to_hyperset()


def test_the_variable_component_is_always_empty() -> None:
    from grounded_hyperset_theory.meta import _unpack_pair as unpack

    for name in ["x", "y", "someLongVariableName", 7]:
        obj = Abstraction(variable=Node(name), body=von_neumann_ordinal(2)).to_hyperset()
        _tag, inner = unpack(obj)
        var, _body = unpack(inner)
        assert var == EmptyHyperset(), name


def test_the_tag_is_one() -> None:
    tag, _ = _unpack_pair(identity_abstraction().to_hyperset())
    assert tag == von_neumann_ordinal(1)


def test_the_body_survives_objectification() -> None:
    """What is preserved: the body, up to bisimulation."""
    body = von_neumann_ordinal(3)
    obj = Abstraction(variable=Node("x"), body=body).to_hyperset()
    _tag, inner = _unpack_pair(obj)
    _var, recovered = _unpack_pair(inner)
    assert recovered == body


def test_abstract_then_instantiate_restores_the_original() -> None:
    """Beta-reduction round trip: pull out the node for 2, then put 2 back."""
    three = von_neumann_ordinal(3)
    ab = abstract(three, parameter=2, var_name="x")
    assert ab.instantiate(von_neumann_ordinal(2)) == three


def test_abstracting_a_different_node_does_not_restore_it() -> None:
    """The control. Abstracting the node for 1 and supplying 2 gives {0,2},
    not 3 -- so the test above is measuring substitution, not a tautology."""
    three = von_neumann_ordinal(3)
    ab = abstract(three, parameter=1, var_name="x")
    assert ab.instantiate(von_neumann_ordinal(2)) != three


def test_abstracting_the_root_gives_the_bare_variable() -> None:
    three = von_neumann_ordinal(3)
    ab = abstract(three, parameter=3, var_name="x")
    assert ab.instantiate(von_neumann_ordinal(2)) == von_neumann_ordinal(2)


def test_instantiating_an_absent_variable_returns_the_body_unchanged() -> None:
    body = von_neumann_ordinal(2)
    ab = Abstraction(variable=Node("nowhere"), body=body)
    assert ab.instantiate(von_neumann_ordinal(3)) == body


def test_instantiate_and_call_agree() -> None:
    ab = identity_abstraction()
    arg = von_neumann_ordinal(2)
    assert ab(arg) == ab.instantiate(arg)


def test_instantiating_with_a_cyclic_argument() -> None:
    """Substitution must survive a non-well-founded argument."""
    ab = identity_abstraction()
    assert ab(QuineAtom()) == QuineAtom()


# ==========================================================================
# 4. meta_fractalize iterates the top level; it does not recurse
# ==========================================================================


def double(h: Hyperset) -> list[Hyperset]:
    return [h, Hyperset.from_elements(h)]


SEED = Hyperset.from_elements(Hyperset.from_elements(EmptyHyperset()))


@pytest.mark.parametrize("depth", [0, 1, 2, 3])
def test_members_never_grow_below_the_top_level(depth: int) -> None:
    """Every member of the seed has one member, and still does at any depth."""
    out = meta_fractalize(SEED, double, depth=depth)
    assert {len(m) for m in out.members()} == {1}


@pytest.mark.parametrize("depth,expected", [(0, 1), (1, 2), (2, 3), (3, 4)])
def test_the_top_level_is_what_grows(depth: int, expected: int) -> None:
    assert len(meta_fractalize(SEED, double, depth=depth)) == expected


def test_depth_zero_is_the_seed() -> None:
    assert meta_fractalize(SEED, double, depth=0) == SEED


@pytest.mark.parametrize("depth", [-1, -5])
def test_negative_depth_is_the_seed(depth: int) -> None:
    assert meta_fractalize(SEED, double, depth=depth) == SEED


def test_the_identity_rule_is_a_fixed_point() -> None:
    assert meta_fractalize(SEED, lambda h: [h], depth=5) == SEED


def test_a_mapping_rule_is_looked_up_by_bisimulation() -> None:
    """The key is a hyperset, and hyperset equality is bisimulation, so a key
    built a different way still matches."""
    one_a = von_neumann_ordinal(1)
    one_b = Hyperset.from_elements(EmptyHyperset())
    assert one_a == one_b
    seed = Hyperset.from_elements(one_a)
    out = meta_fractalize(seed, {one_b: [von_neumann_ordinal(2)]}, depth=1)
    assert out == Hyperset.from_elements(von_neumann_ordinal(2))


def test_a_mapping_leaves_unlisted_members_alone() -> None:
    seed = Hyperset.from_elements(von_neumann_ordinal(1), von_neumann_ordinal(2))
    out = meta_fractalize(seed, {von_neumann_ordinal(1): [von_neumann_ordinal(3)]}, depth=1)
    assert out == Hyperset.from_elements(von_neumann_ordinal(3), von_neumann_ordinal(2))


def test_the_empty_seed_stays_empty() -> None:
    assert meta_fractalize(EmptyHyperset(), double, depth=4) == EmptyHyperset()


# ==========================================================================
# 5. objectify_apg round-trips the shape and nothing else
# ==========================================================================

SHAPES = [
    ("single node", {"r": []}, "r"),
    ("singleton", {"r": ["e"], "e": []}, "r"),
    ("omega", {"w": ["w"]}, "w"),
    ("diamond", {"r": ["a", "b"], "a": ["d"], "b": ["d"], "d": []}, "r"),
    ("two-cycle", {"p": ["q"], "q": ["p"]}, "p"),
    ("chain", {"r": ["a"], "a": ["b"], "b": []}, "r"),
]


@pytest.mark.parametrize("name,edges,root", SHAPES)
def test_the_round_trip_preserves_the_set(name: str, edges: dict[str, list[str]], root: str) -> None:
    g = graph(edges, root)
    assert bisimilar(g, deobjectify_apg(objectify_apg(g))), name


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_the_round_trip_preserves_ordinals(n: int) -> None:
    g = von_neumann_ordinal(n).apg
    assert Hyperset(deobjectify_apg(objectify_apg(g))) == von_neumann_ordinal(n)


@pytest.mark.parametrize("name,edges,root", SHAPES)
def test_the_round_trip_preserves_the_node_count(name: str, edges: dict[str, list[str]], root: str) -> None:
    g = graph(edges, root)
    assert len(deobjectify_apg(objectify_apg(g)).nodes) == len(g.nodes), name


def test_labels_do_not_survive() -> None:
    """Which is what "up to isomorphism" costs, and it is not obvious."""
    r = Node("r", label="ROOT")
    c = Node("c", label="CHILD")
    g = AccessiblePointedGraph(root=r, edges={r: [c], c: []})
    back = deobjectify_apg(objectify_apg(g))
    assert all(n.label is None for n in back.nodes)


def test_node_identities_do_not_survive() -> None:
    r = Node("r", label="ROOT")
    c = Node("c", label="CHILD")
    g = AccessiblePointedGraph(root=r, edges={r: [c], c: []})
    back = deobjectify_apg(objectify_apg(g))
    assert r not in back.nodes


def test_two_graphs_with_the_same_shape_encode_identically() -> None:
    a = graph({"r": ["x"], "x": []}, "r")
    b = graph({"p": ["q"], "q": []}, "p")
    assert objectify_apg(a) == objectify_apg(b)


def test_two_graphs_with_different_shapes_encode_differently() -> None:
    a = graph({"r": ["x"], "x": []}, "r")
    b = graph({"r": ["x", "y"], "x": [], "y": ["x"]}, "r")
    assert objectify_apg(a) != objectify_apg(b)


# ==========================================================================
# 6. Kuratowski pairs: unpack inverts pair, and refuses what is not a pair
# ==========================================================================

SMALL = [von_neumann_ordinal(i) for i in range(4)] + [QuineAtom(), EmptyHyperset()]


@pytest.mark.parametrize("i", range(len(SMALL)))
@pytest.mark.parametrize("j", range(len(SMALL)))
def test_unpack_inverts_pair(i: int, j: int) -> None:
    a, b = SMALL[i], SMALL[j]
    x, y = _unpack_pair(pair(a, b))
    assert x == a and y == b


def test_the_diagonal_case_is_the_one_that_degenerates() -> None:
    """(a, a) = {{a}, {a, a}} = {{a}}: one member, not two."""
    a = von_neumann_ordinal(2)
    assert len(pair(a, a)) == 1
    assert _unpack_pair(pair(a, a)) == (a, a)


@pytest.mark.parametrize(
    "bad",
    [
        "two singletons",
        "two doubletons",
        "three members",
        "singleton of a doubleton mismatch",
    ],
)
def test_a_non_pair_is_refused(bad: str) -> None:
    zero, one, two = (von_neumann_ordinal(i) for i in range(3))
    cases = {
        "two singletons": Hyperset.from_elements(
            Hyperset.from_elements(zero), Hyperset.from_elements(one)
        ),
        "two doubletons": Hyperset.from_elements(
            Hyperset.from_elements(zero, one), Hyperset.from_elements(one, two)
        ),
        "three members": Hyperset.from_elements(
            Hyperset.from_elements(zero),
            Hyperset.from_elements(one),
            Hyperset.from_elements(two),
        ),
        "singleton of a doubleton mismatch": Hyperset.from_elements(
            Hyperset.from_elements(zero, one, two)
        ),
    }
    with pytest.raises(ValueError, match="Malformed Kuratowski pair"):
        _unpack_pair(cases[bad])


# ==========================================================================
# 7. Relations and functions
# ==========================================================================


def test_a_relation_round_trips() -> None:
    pairs = [(von_neumann_ordinal(i), von_neumann_ordinal(i + 1)) for i in range(3)]
    back = deobjectify_relation(objectify_relation(pairs))
    assert sorted((a.to_int(), b.to_int()) for a, b in back) == [(0, 1), (1, 2), (2, 3)]


def test_direction_is_preserved() -> None:
    """(0,1) and (1,0) must not be confused, which is the whole point of pairs."""
    fwd = objectify_relation([(von_neumann_ordinal(0), von_neumann_ordinal(1))])
    rev = objectify_relation([(von_neumann_ordinal(1), von_neumann_ordinal(0))])
    assert fwd != rev
    assert deobjectify_relation(fwd)[0][0].to_int() == 0
    assert deobjectify_relation(rev)[0][0].to_int() == 1


def test_an_empty_relation_round_trips() -> None:
    assert deobjectify_relation(objectify_relation([])) == []


def test_a_repeated_pair_decodes_twice_although_the_set_holds_it_once() -> None:
    """The members()/len() split, inside one round trip.

    ``from_elements`` builds one child node per argument and does not merge
    bisimilar ones, so a relation given the same pair twice has two child nodes.
    ``len`` quotients and says 1; ``deobjectify_relation`` iterates ``members()``
    and returns 2. Both are reporting honestly about different things, and the
    function's own two answers disagree.
    """
    p = (von_neumann_ordinal(0), von_neumann_ordinal(1))
    rel = objectify_relation([p, p])
    assert len(rel) == 1
    assert len(deobjectify_relation(rel)) == 2
    a, b = deobjectify_relation(rel)
    assert a == b


def test_from_elements_does_not_merge_bisimilar_arguments() -> None:
    """The root cause, stated on its own."""
    x = von_neumann_ordinal(2)
    both = Hyperset.from_elements(x, x)
    assert len(both) == 1
    assert len(both.members()) == 2


def test_a_function_round_trips() -> None:
    mapping = {von_neumann_ordinal(i): von_neumann_ordinal(i * 2) for i in range(3)}
    back = deobjectify_function(objectify_function(mapping))
    assert {k.to_int(): v.to_int() for k, v in back.items()} == {0: 0, 1: 2, 2: 4}


def test_a_multivalued_relation_is_refused() -> None:
    """The docstring says it verifies single-valuedness. It does."""
    bad = Hyperset.from_elements(
        pair(von_neumann_ordinal(0), von_neumann_ordinal(1)),
        pair(von_neumann_ordinal(0), von_neumann_ordinal(2)),
    )
    with pytest.raises(ValueError, match="single-valued|well-defined"):
        deobjectify_function(bad)


def test_a_repeated_identical_entry_is_not_a_conflict() -> None:
    """Same domain, same codomain, stated twice, is still a function."""
    p = pair(von_neumann_ordinal(0), von_neumann_ordinal(1))
    assert len(deobjectify_function(Hyperset.from_elements(p, p))) == 1


def test_the_conflict_check_uses_bisimulation_not_identity() -> None:
    """0 built two different ways is one domain element, so this must fire."""
    zero_a = von_neumann_ordinal(0)
    zero_b = EmptyHyperset()
    assert zero_a == zero_b
    bad = Hyperset.from_elements(
        pair(zero_a, von_neumann_ordinal(1)),
        pair(zero_b, von_neumann_ordinal(2)),
    )
    with pytest.raises(ValueError, match="single-valued|well-defined"):
        deobjectify_function(bad)


# ==========================================================================
# 8. members() is the graph view and len() is the set view
# ==========================================================================


def test_members_can_outnumber_len() -> None:
    """Two distinct childless children are one member and two entries."""
    h = hyperset({"r": ["p", "q"], "p": [], "q": []}, "r")
    assert len(h.members()) == 2
    assert len(h) == 1


def test_and_the_set_is_the_singleton_of_the_empty_set() -> None:
    h = hyperset({"r": ["p", "q"], "p": [], "q": []}, "r")
    assert h == Hyperset.from_elements(EmptyHyperset())


def test_the_same_split_shows_up_in_the_shipped_patterns() -> None:
    s = fractal_hyperset("sierpinski")
    assert len(s.members()) == 2 and len(s) == 1


def test_cardinality_and_len_agree() -> None:
    """They are the same call; this pins that they stay so."""
    h = hyperset({"r": ["p", "q"], "p": [], "q": []}, "r")
    assert h.cardinality() == len(h)


def test_deobjectify_relation_inherits_the_duplication() -> None:
    """It iterates members(), so a relation graph with bisimilar sibling nodes
    yields the same pair more than once even though the set has it once."""
    p = pair(von_neumann_ordinal(0), von_neumann_ordinal(1))
    root = Node("rel")
    left = Node("l")
    right = Node("r")
    # Two separate copies of the same pair, as distinct nodes.
    edges: dict[Node, list[Node]] = {root: [left, right]}
    for tag, sub in (("l", left), ("r", right)):
        offset = {n: Node((tag, n.id)) for n in p.apg.nodes}
        for n in p.apg.nodes:
            mapped = sub if n == p.apg.root else offset[n]
            edges[mapped] = [
                sub if c == p.apg.root else offset[c] for c in p.apg.children(n)
            ]
    rel = Hyperset(AccessiblePointedGraph(root=root, edges=edges))
    assert len(rel) == 1
    assert len(deobjectify_relation(rel)) == 2
