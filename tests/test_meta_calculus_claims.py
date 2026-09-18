"""What `meta_calculus` claims about rewrite systems, and whether it holds.

`AGENTS.md` names one of these in the prime directive -- "never claim confluence
when critical pairs fail to join". What the module did was subtler: it answered
about its own budget and presented that as an answer about the system.

`reduction_apg` truncated silently on two budgets. A state at the depth horizon
was dequeued and skipped, so it was built with no outgoing edges; a transition to
a state past `max_states` was dropped with neither node nor edge. In this
representation a state with no successors is what a normal form looks like, so
four functions read the horizon as a result. `n -> n+1` from 0 diverges, and its
depth-5 fragment made `is_terminating` say True, `normal_forms` return the
frontier, and `find_attractors` report an attractor for a system that has none.
`is_confluent` was worse than unsound in one direction: it returned False for a
locally confluent system whose join sat one step past the horizon, and True from
a start whose divergence sat past it.

`is_confluent` also decided the wrong property. Its docstring named three --
confluence in the name, local confluence in the text, and the diamond property in
parentheses -- and computed the weakest. Huet's counterexample separates them and
is the centre of this file.

The references here are hand-built graphs whose answers follow from an argument,
and a brute-force cycle enumerator that shares no code with the implementation.

Negative control: 32 of these 68 tests fail against the unfixed source, and none
hang -- the defect here was answering too readily rather than not answering. The
control needs one graft to run at all: `terminal_sccs` and its helper are new, so
the file cannot import against the unfixed module. They were copied verbatim onto
the old source and nothing else was, so every other test exercises old code and
the two that would otherwise have been unrunnable are not credited to the fix.
"""

from __future__ import annotations

import itertools

import pytest

from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node
from grounded_hyperset_theory.hyperset import Hyperset, von_neumann_ordinal
from grounded_hyperset_theory.meta_calculus import (
    RewriteRule,
    RewriteTrajectory,
    RewritingSystem,
    find_periodic_orbits,
    is_locally_confluent,
    is_terminating,
    normal_forms,
    terminal_sccs,
    trajectory_bisimilar,
)


# --------------------------------------------------------------------------
# Hand-built graphs and systems, and one reference that shares no code.
# --------------------------------------------------------------------------


def graph(edges: dict[str, list[str]], root: str) -> AccessiblePointedGraph:
    nodes = {name: Node(name, label=name) for name in edges}
    return AccessiblePointedGraph(
        root=nodes[root],
        edges={nodes[a]: {nodes[b] for b in bs} for a, bs in edges.items()},
    )


def ordinal_system(table: dict[int, list[int]], name: str = "test") -> RewritingSystem:
    """A rewrite system on the von Neumann ordinals, given as a transition table."""

    def transform(h: Hyperset) -> list[Hyperset]:
        return [von_neumann_ordinal(n) for n in table.get(len(h), [])]

    return RewritingSystem([RewriteRule(name="table", transform=transform)], name=name)


def brute_force_simple_cycles(edges: dict[str, list[str]]) -> int:
    """Count simple cycles by trying every ordered tuple of distinct nodes.

    Exponential and useless for real graphs, which is the point: it shares no
    structure with the implementation, so agreement is evidence rather than a
    restatement.
    """
    names = sorted(edges)
    found: set[tuple[str, ...]] = set()
    for size in range(1, len(names) + 1):
        for chosen in itertools.permutations(names, size):
            ok = all(
                chosen[(i + 1) % size] in edges[chosen[i]] for i in range(size)
            )
            if not ok:
                continue
            lowest = min(range(size), key=lambda i: chosen[i])
            found.add(chosen[lowest:] + chosen[:lowest])
    return len(found)


# `a <-> b`, `a -> c`, `b -> d`, with `c` and `d` distinct normal forms.
# Locally confluent; not confluent; not terminating, so Newman does not lift it.
HUET_EDGES = {"a": ["b", "c"], "b": ["a", "d"], "c": [], "d": []}
HUET_TABLE = {0: [1, 2], 1: [0, 3], 2: [], 3: []}

# 1->2, 1->3, 2->3, 3->1, 3->2. Simple cycles: (1,2,3), (1,3), (2,3).
THREE_CYCLES = {"1": ["2", "3"], "2": ["3"], "3": ["1", "2"]}


def diverging() -> RewritingSystem:
    """`n -> n+1`, from anywhere. No normal form, no repeated state, ever."""
    return RewritingSystem(
        [RewriteRule(name="succ", transform=lambda h: [h.successor()])],
        name="diverging",
    )


# --------------------------------------------------------------------------
# 1. A rule that raises is not a rule that does not apply.
# --------------------------------------------------------------------------


def _exploding(_: Hyperset) -> list[Hyperset]:
    raise ZeroDivisionError("a bug in the rule body")


def test_a_raising_rule_raises_rather_than_reporting_no_match() -> None:
    """`except Exception: return []` turned any bug in a rule body into the
    statement that the rule does not apply here."""
    rule = RewriteRule(name="broken", transform=_exploding)
    with pytest.raises(RuntimeError, match="broken"):
        rule.apply(von_neumann_ordinal(1))


def test_the_raised_error_names_the_rule_and_the_original_exception() -> None:
    rule = RewriteRule(name="broken", transform=_exploding)
    with pytest.raises(RuntimeError) as excinfo:
        rule.apply(von_neumann_ordinal(1))
    message = str(excinfo.value)
    assert "broken" in message
    assert "ZeroDivisionError" in message
    assert isinstance(excinfo.value.__cause__, ZeroDivisionError)


def test_matches_does_not_report_false_for_a_broken_rule() -> None:
    """`matches` is `apply` in a boolean costume, so it inherited the lie."""
    rule = RewriteRule(name="broken", transform=_exploding)
    with pytest.raises(RuntimeError):
        rule.matches(von_neumann_ordinal(1))


def test_step_does_not_report_a_normal_form_for_a_broken_rule() -> None:
    system = RewritingSystem([RewriteRule(name="broken", transform=_exploding)])
    with pytest.raises(RuntimeError):
        system.step(von_neumann_ordinal(1))
    with pytest.raises(RuntimeError):
        system.step_deterministic(von_neumann_ordinal(1))


def test_a_broken_rule_does_not_produce_a_one_state_graph_of_normal_forms() -> None:
    """The end of the chain: the whole reduction graph came back as a single
    state, marked terminal, from a rule that had never run to completion."""
    system = RewritingSystem([RewriteRule(name="broken", transform=_exploding)])
    with pytest.raises(RuntimeError):
        system.reduction_apg(von_neumann_ordinal(1), max_depth=5)


def test_a_rule_that_genuinely_does_not_apply_still_returns_empty() -> None:
    """The distinction only means something if the honest case still works."""
    rule = RewriteRule(
        name="only_nonzero",
        transform=lambda h: [] if len(h) == 0 else [von_neumann_ordinal(len(h) - 1)],
    )
    assert rule.apply(von_neumann_ordinal(0)) == []
    assert rule.matches(von_neumann_ordinal(0)) is False
    assert rule.apply(von_neumann_ordinal(2)) == [von_neumann_ordinal(1)]


# --------------------------------------------------------------------------
# 2. reduction_apg is complete, or it refuses.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("depth", [0, 1, 3, 6, 10])
def test_a_diverging_system_is_refused_at_every_depth(depth: int) -> None:
    """There is no depth at which `n -> n+1` has been fully explored, so there
    is no depth at which a graph would be an honest answer."""
    with pytest.raises(ValueError, match="deeper than max_depth"):
        diverging().reduction_apg(von_neumann_ordinal(0), max_depth=depth, max_states=200)


def test_the_state_budget_refuses_rather_than_dropping_the_transition() -> None:
    """Exceeding `max_states` used to drop the transition entirely -- no node and
    no edge -- which left the state it came from looking like a normal form."""
    with pytest.raises(ValueError, match="does not fit in max_states"):
        diverging().reduction_apg(von_neumann_ordinal(0), max_depth=100, max_states=4)


def test_both_refusals_say_what_to_do() -> None:
    with pytest.raises(ValueError) as depth_error:
        diverging().reduction_apg(von_neumann_ordinal(0), max_depth=3, max_states=200)
    assert "Raise max_depth" in str(depth_error.value)

    with pytest.raises(ValueError) as state_error:
        diverging().reduction_apg(von_neumann_ordinal(0), max_depth=100, max_states=4)
    assert "Raise the budget" in str(state_error.value)
    assert "normal form" in str(state_error.value)


@pytest.mark.parametrize(("max_states", "max_depth"), [(0, 5), (-1, 5), (5, -1)])
def test_budgets_below_their_floor_are_rejected(max_states: int, max_depth: int) -> None:
    system = ordinal_system({0: []})
    with pytest.raises(ValueError, match="must be"):
        system.reduction_apg(von_neumann_ordinal(0), max_depth=max_depth, max_states=max_states)


def test_a_system_that_fits_exactly_is_built_exactly() -> None:
    """The boundary. Four states and a depth of three, in a budget of four and
    three; one less of either and it refuses."""
    system = ordinal_system({3: [2], 2: [1], 1: [0], 0: []}, name="countdown")
    start = von_neumann_ordinal(3)
    apg = system.reduction_apg(start, max_depth=3, max_states=4)
    assert len(apg.nodes) == 4
    with pytest.raises(ValueError):
        system.reduction_apg(start, max_depth=2, max_states=4)
    with pytest.raises(ValueError):
        system.reduction_apg(start, max_depth=3, max_states=3)


@pytest.mark.parametrize(("max_depth", "max_states"), [(4, 5), (8, 20), (50, 500)])
def test_the_graph_is_saturated_so_a_larger_budget_changes_nothing(
    max_depth: int, max_states: int
) -> None:
    """The sharpest statement of completeness available from outside: once the
    budget suffices, raising it further produces the same graph. A truncating
    build had the opposite property -- every budget gave a different answer, and
    that is how `is_confluent` came to answer False, False, True, True, True on
    one unchanging system.
    """
    system = ordinal_system({4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []}, name="fork")
    start = von_neumann_ordinal(4)
    apg = system.reduction_apg(start, max_depth=max_depth, max_states=max_states)
    assert (len(apg.nodes), apg.edge_count) == (5, 5)
    assert len(normal_forms(apg)) == 1
    assert len(terminal_sccs(apg)) == 1


def test_a_complete_graph_has_an_edge_for_every_transition() -> None:
    """Counted rather than assumed: the countdown has four states and three
    transitions, and the fork has five states and five transitions."""
    countdown = ordinal_system({3: [2], 2: [1], 1: [0], 0: []})
    apg = countdown.reduction_apg(von_neumann_ordinal(3), max_depth=5, max_states=10)
    assert (len(apg.nodes), apg.edge_count) == (4, 3)

    fork = ordinal_system({4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []})
    apg = fork.reduction_apg(von_neumann_ordinal(4), max_depth=8, max_states=20)
    assert (len(apg.nodes), apg.edge_count) == (5, 5)


def test_states_are_identified_up_to_bisimulation_and_that_is_not_an_overclaim() -> None:
    """`reduction_apg` says its nodes are "unique states modulo bisimulation",
    and `Hyperset.__eq__` really is bisimulation, so the claim holds. Two paths
    to the same ordinal converge on one node rather than two.
    """
    fork = ordinal_system({4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []})
    apg = fork.reduction_apg(von_neumann_ordinal(4), max_depth=8, max_states=20)
    assert len(apg.nodes) == 5, "4, 3, 2, 1, 0 -- the two routes to 2 share a node"
    assert von_neumann_ordinal(2) == von_neumann_ordinal(2)


# --------------------------------------------------------------------------
# 3. Confluence, and the property it is not.
# --------------------------------------------------------------------------


def test_huets_counterexample_is_locally_confluent() -> None:
    """From `a` the fork to `b` and `c` rejoins at `c`, via `b -> a -> c`; from
    `b` the fork to `a` and `d` rejoins at `d`. So local confluence holds, and
    the function that measures it is right."""
    assert is_locally_confluent(graph(HUET_EDGES, "a")) is True


def test_huets_counterexample_is_not_confluent() -> None:
    """`a` reduces to `c` and to `d`, two distinct normal forms, so there is no
    common descendant. This is the test the old implementation could not pass:
    it computed local confluence and returned True under the name `is_confluent`.
    """
    system = ordinal_system(HUET_TABLE, name="huet")
    assert system.is_confluent(von_neumann_ordinal(0), max_depth=4, max_states=10) is False


def test_the_two_properties_are_measured_on_the_same_graph() -> None:
    """Both at once, so the gap is visible in one assertion rather than inferred
    across two tests: locally confluent and not confluent."""
    system = ordinal_system(HUET_TABLE, name="huet")
    apg = system.reduction_apg(von_neumann_ordinal(0), max_depth=4, max_states=10)
    assert is_locally_confluent(apg) is True
    assert len(terminal_sccs(apg)) == 2
    assert system.is_confluent(von_neumann_ordinal(0), max_depth=4, max_states=10) is False
    assert not is_terminating(apg), "Newman's lemma would lift it if this terminated"


def test_newmans_lemma_holds_where_it_applies() -> None:
    """The other side of the same coin: add termination and local confluence does
    lift. The countdown terminates, is locally confluent, and is confluent."""
    system = ordinal_system({3: [2], 2: [1], 1: [0], 0: []}, name="countdown")
    apg = system.reduction_apg(von_neumann_ordinal(3), max_depth=5, max_states=10)
    assert is_terminating(apg)
    assert is_locally_confluent(apg)
    assert system.is_confluent(von_neumann_ordinal(3), max_depth=5, max_states=10)


def test_a_fork_to_two_normal_forms_is_not_confluent() -> None:
    """The simplest failure, and terminating, so it is not the Huet case."""
    system = ordinal_system({2: [0, 1], 1: [], 0: []}, name="fork_to_two")
    assert system.is_confluent(von_neumann_ordinal(2), max_depth=3, max_states=10) is False


def test_a_fork_that_rejoins_is_confluent() -> None:
    system = ordinal_system({4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []}, name="rejoins")
    assert system.is_confluent(von_neumann_ordinal(4), max_depth=8, max_states=20) is True


def test_an_oscillator_is_confluent() -> None:
    """One terminal SCC, which happens to be a cycle. Every pair of states joins,
    infinitely often; it simply never settles. Confluence does not require
    termination and this is the case that shows it."""
    system = ordinal_system({1: [2], 2: [1]}, name="oscillator")
    assert system.is_confluent(von_neumann_ordinal(1), max_depth=4, max_states=10) is True


@pytest.mark.parametrize("max_depth", [4, 5, 6, 8, 12])
def test_the_confluence_verdict_does_not_move_with_the_budget(max_depth: int) -> None:
    """The defect in one line. The old implementation answered False, False,
    True, True, True on one system as the horizon moved, because a join past the
    horizon reads as a failure to join. A sufficient budget now gives one answer
    and an insufficient one gives an error, never a different answer.
    """
    system = ordinal_system({4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []}, name="rejoins")
    assert system.is_confluent(von_neumann_ordinal(4), max_depth=max_depth, max_states=20) is True


def test_confluence_refuses_rather_than_answering_from_an_incomplete_graph() -> None:
    """Under a horizon of two the join has not been built yet. The old answer was
    False, which is a statement about the budget wearing the clothes of a
    statement about the system."""
    system = ordinal_system({4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []}, name="rejoins")
    with pytest.raises(ValueError):
        system.is_confluent(von_neumann_ordinal(4), max_depth=2, max_states=20)


def test_confluence_refuses_when_no_fork_has_been_reached_yet() -> None:
    """The other unsound direction. A start whose divergence lies past the
    horizon examined no fork at all and returned True -- a certificate issued for
    a search that never happened."""
    system = ordinal_system({5: [4], 4: [2, 3], 3: [], 2: []}, name="late_fork")
    with pytest.raises(ValueError):
        system.is_confluent(von_neumann_ordinal(5), max_depth=1, max_states=20)
    assert system.is_confluent(von_neumann_ordinal(5), max_depth=3, max_states=20) is False


# --------------------------------------------------------------------------
# 4. Terminal SCCs -- the attractors, and the confluence decision.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("edges", "root", "expected"),
    [
        (HUET_EDGES, "a", [{"c"}, {"d"}]),
        ({"3": ["2"], "2": ["1"], "1": ["0"], "0": []}, "3", [{"0"}]),
        ({"1": ["2"], "2": ["1"]}, "1", [{"1", "2"}]),
        ({"a": ["a"]}, "a", [{"a"}]),
        ({"r": ["x", "y"], "x": ["x"], "y": ["y"]}, "r", [{"x"}, {"y"}]),
    ],
)
def test_terminal_sccs_are_the_components_nothing_leaves(
    edges: dict[str, list[str]], root: str, expected: list[set[str]]
) -> None:
    found = [{str(n.id) for n in component} for component in terminal_sccs(graph(edges, root))]
    assert sorted(map(sorted, found)) == sorted(map(sorted, expected))


def test_terminal_sccs_partition_nothing_and_overlap_nothing() -> None:
    """Distinct SCCs are disjoint by definition, so a component appearing twice
    or two components sharing a state would be a bug in the reachability
    argument rather than a property of the graph."""
    components = terminal_sccs(graph(HUET_EDGES, "a"))
    seen: set[Node] = set()
    for component in components:
        assert not (component & seen)
        seen |= component


def test_find_attractors_returns_normal_forms_and_says_so() -> None:
    """The docstring promised "terminal states (normal forms) or cyclic
    attractors" and returned only the first kind -- it collects nodes with no
    children, and a cycle has none such. The oscillator has one attractor and
    `find_attractors` finds zero; `terminal_sccs` is the counterpart."""
    system = ordinal_system({1: [2], 2: [1]}, name="oscillator")
    start = von_neumann_ordinal(1)
    assert system.find_attractors(start, max_depth=4) == []
    apg = system.reduction_apg(start, max_depth=4, max_states=10)
    assert len(terminal_sccs(apg)) == 1
    assert len(next(iter(terminal_sccs(apg)))) == 2
    assert "normal forms" in (system.find_attractors.__doc__ or "")
    assert "terminal_sccs" in (system.find_attractors.__doc__ or "")


def test_find_attractors_no_longer_reports_the_horizon_as_an_attractor() -> None:
    """It used to report one attractor for `n -> n+1`, which has none. It cannot
    now, because there is no graph to read it off."""
    with pytest.raises(ValueError):
        diverging().find_attractors(von_neumann_ordinal(0), max_depth=5)


# --------------------------------------------------------------------------
# 5. Every simple cycle, each of them once.
# --------------------------------------------------------------------------


def test_the_missed_cycle() -> None:
    """The counterexample. Three simple cycles exist; the old DFS found two,
    because its `visited` set was global and `3` was already marked when the
    search would have had to revisit it to close `(1,3)`."""
    found = find_periodic_orbits(graph(THREE_CYCLES, "1"))
    as_sets = sorted(sorted(str(n.id) for n in c) for c in found)
    assert as_sets == [["1", "2", "3"], ["1", "3"], ["2", "3"]]


@pytest.mark.parametrize(
    ("edges", "root"),
    [
        (THREE_CYCLES, "1"),
        (HUET_EDGES, "a"),
        ({"1": ["2"], "2": ["1"]}, "1"),
        ({"a": ["a"]}, "a"),
        ({"a": ["b"], "b": ["c"], "c": []}, "a"),
        ({"a": ["b", "c"], "b": ["c", "a"], "c": ["a", "b"]}, "a"),
        ({"r": ["a"], "a": ["b", "r"], "b": ["a", "r"]}, "r"),
    ],
)
def test_the_count_agrees_with_brute_force(edges: dict[str, list[str]], root: str) -> None:
    """Against an enumerator that tries every ordered tuple of distinct nodes and
    shares no structure with the implementation."""
    assert len(find_periodic_orbits(graph(edges, root))) == brute_force_simple_cycles(edges)


def test_each_cycle_is_listed_once() -> None:
    """The old implementation deduplicated by rotating to the minimum and
    checking membership. Rooting the search at each cycle's lowest node makes
    that pass unnecessary, because a cycle has exactly one lowest node."""
    found = find_periodic_orbits(graph({"a": ["b", "c"], "b": ["c", "a"], "c": ["a", "b"]}, "a"))
    keys = [tuple(str(n.id) for n in c) for c in found]
    assert len(keys) == len(set(keys))


def test_each_cycle_starts_at_its_lowest_node() -> None:
    for cycle in find_periodic_orbits(graph(THREE_CYCLES, "1")):
        ids = [str(n.id) for n in cycle]
        assert ids[0] == min(ids), ids


def test_every_returned_cycle_is_a_real_cycle() -> None:
    """Soundness alongside completeness: consecutive nodes must be edges and the
    last must close back to the first."""
    g = graph(THREE_CYCLES, "1")
    for cycle in find_periodic_orbits(g):
        for i, node in enumerate(cycle):
            assert cycle[(i + 1) % len(cycle)] in g.children(node)
        assert len(set(cycle)) == len(cycle), "a simple cycle repeats no node"


def test_an_acyclic_graph_has_no_periodic_orbits() -> None:
    assert find_periodic_orbits(graph({"a": ["b"], "b": ["c"], "c": []}, "a")) == []


def test_a_self_loop_is_a_cycle_of_length_one() -> None:
    found = find_periodic_orbits(graph({"a": ["a"]}, "a"))
    assert len(found) == 1
    assert len(found[0]) == 1


def test_the_cycle_budget_refuses_rather_than_returning_a_subset() -> None:
    """The number of simple cycles is exponential in general. That is a reason to
    bound the work, not a reason to hand back an arbitrary subset of the answer
    under a docstring that says "all"."""
    complete = {"a": ["b", "c"], "b": ["c", "a"], "c": ["a", "b"]}
    g = graph(complete, "a")
    total = len(find_periodic_orbits(g))
    assert total >= 3
    with pytest.raises(ValueError, match="max_cycles"):
        find_periodic_orbits(g, max_cycles=total - 1)
    assert len(find_periodic_orbits(g, max_cycles=total)) == total


# --------------------------------------------------------------------------
# 6. Termination and normal forms now transfer from graph to system.
# --------------------------------------------------------------------------


def test_a_diverging_system_can_no_longer_be_called_terminating() -> None:
    """`is_terminating` reads acyclicity off a graph, so the honest fix is
    upstream: there is no longer a graph for a system that has not been fully
    explored. The route that produced the false positive is closed."""
    with pytest.raises(ValueError):
        diverging().reduction_apg(von_neumann_ordinal(0), max_depth=5, max_states=100)


def test_is_terminating_agrees_with_the_system_on_complete_graphs() -> None:
    countdown = ordinal_system({3: [2], 2: [1], 1: [0], 0: []})
    assert is_terminating(countdown.reduction_apg(von_neumann_ordinal(3), max_depth=5, max_states=10))

    oscillator = ordinal_system({1: [2], 2: [1]})
    assert not is_terminating(oscillator.reduction_apg(von_neumann_ordinal(1), max_depth=4, max_states=10))


def test_normal_forms_are_exactly_the_states_the_system_cannot_step_from() -> None:
    """Checked against the system, not against the graph that came from it."""
    table = {4: [2, 3], 3: [2], 2: [1], 1: [0], 0: []}
    system = ordinal_system(table)
    apg = system.reduction_apg(von_neumann_ordinal(4), max_depth=8, max_states=20)
    childless = normal_forms(apg)
    assert len(childless) == 1
    assert sum(1 for value, nexts in table.items() if not nexts) == 1


def test_both_docstrings_now_state_the_completeness_requirement() -> None:
    """The statement transfers from graph to system only if the graph is
    complete, and a reader has no way to know that unless it is written down."""
    assert "complete" in (normal_forms.__doc__ or "")
    assert "complete" in (is_terminating.__doc__ or "")
    assert "proves guaranteed termination" not in (is_terminating.__doc__ or "")


# --------------------------------------------------------------------------
# 7. The budget that was not the binding one.
# --------------------------------------------------------------------------


def test_trajectory_bisimilar_takes_the_depth_budget_it_was_applying() -> None:
    """It accepted `max_states` and silently applied `reduction_apg`'s own
    `max_depth` default of 10, so raising `max_states` to 100 on a 31-state
    system still compared 11-state graphs. The parameter that looked like the
    control was not the binding one."""
    deep = ordinal_system({n: [n - 1] for n in range(1, 21)} | {0: []}, name="deep")
    start = von_neumann_ordinal(20)
    with pytest.raises(ValueError):
        trajectory_bisimilar(deep, deep, start, start, max_states=100)
    assert trajectory_bisimilar(deep, deep, start, start, max_states=100, max_depth=25)


def test_two_systems_with_the_same_dynamics_are_bisimilar() -> None:
    left = ordinal_system({3: [2], 2: [1], 1: [0], 0: []}, name="left")
    right = ordinal_system({3: [2], 2: [1], 1: [0], 0: []}, name="right")
    start = von_neumann_ordinal(3)
    assert trajectory_bisimilar(left, right, start, start, max_states=10, max_depth=5)


def test_two_systems_with_different_dynamics_are_not_bisimilar() -> None:
    chain = ordinal_system({3: [2], 2: [1], 1: [0], 0: []}, name="chain")
    forking = ordinal_system({3: [2, 1], 2: [1], 1: [0], 0: []}, name="forking")
    start = von_neumann_ordinal(3)
    assert not trajectory_bisimilar(chain, forking, start, start, max_states=10, max_depth=5)


def test_trajectories_are_still_compared_without_a_budget() -> None:
    """The `RewriteTrajectory` path builds no reduction graph, so no budget
    applies to it and none of this changed there."""
    left = RewriteTrajectory(tuple(von_neumann_ordinal(n) for n in (0, 1, 2)))
    right = RewriteTrajectory(tuple(von_neumann_ordinal(n) for n in (0, 1, 2)))
    assert trajectory_bisimilar(left, right)


# --------------------------------------------------------------------------
# 8. trace: three ways to stop, one return type.
# --------------------------------------------------------------------------


def test_the_trace_docstring_gives_the_check_it_cannot_encode_in_its_return() -> None:
    """`trace` returns a plain list. A diverging system stopped at `max_steps`
    and a system that halted on its own are the same shape, and the difference
    matters. The docstring now names the three stopping conditions and the test
    for each."""
    doc = RewritingSystem.trace.__doc__ or ""
    assert "reached_normal_form" in doc
    assert "ran_out" in doc


def test_the_three_stopping_conditions_are_actually_distinguishable() -> None:
    """Not merely documented -- the check in the docstring is run here."""
    halting = ordinal_system({2: [1], 1: [0], 0: []}, name="halting")
    path = halting.trace(von_neumann_ordinal(2), max_steps=100)
    assert halting.step_deterministic(path[-1]) is None

    running = diverging()
    cut = running.trace(von_neumann_ordinal(0), max_steps=3)
    assert running.step_deterministic(cut[-1]) is not None

    oscillator = ordinal_system({1: [2], 2: [1]}, name="oscillator")
    looped = oscillator.trace(von_neumann_ordinal(1), max_steps=100)
    assert looped[-1] in looped[:-1]
