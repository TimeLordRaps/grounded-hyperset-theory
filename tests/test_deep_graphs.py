"""Graph traversals must not be bounded by CPython's frame limit.

A hyperset's membership chain is a graph, not a call stack. `has_cycles`,
`topological_sort` and the Tarjan condensation inside `scc_quotient` were all
written recursively, so an APG a few thousand links deep raised RecursionError
instead of answering. A traversal that cannot report on a structure the library
can construct is not a verification-grade traversal.

These tests also check the answers, not merely the absence of a crash: a deep
chain is acyclic, a deep chain closed into a loop is not, the topological order
really is an order, and the condensation of a long cycle is a single point.
"""

from __future__ import annotations

import pytest

from grounded_hyperset_theory.abstraction import refine_to_bisimulation, scc_quotient
from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node

# Comfortably past CPython's default recursion limit of 1000, and past the
# headroom a test runner leaves, without being slow. The traversals fixed here
# are linear, so this costs milliseconds.
DEEP = 5000

# The bisimulation refinement was already iterative, so these cases check its
# answers rather than its stack use. It re-scans every node once per refinement
# round, which is quadratic on a chain, so they run just past the recursion
# limit instead of at DEEP -- see the complexity note in the findings.
BISIM_DEEP = 1200


def _chain(length: int) -> AccessiblePointedGraph:
    """0 -> 1 -> ... -> length, a well-founded membership chain."""
    edges: dict[int, list[int]] = {i: [i + 1] for i in range(length)}
    edges[length] = []
    return AccessiblePointedGraph(root=0, edges=edges)


def _cycle(length: int) -> AccessiblePointedGraph:
    """0 -> 1 -> ... -> length -> 0, a single non-well-founded loop."""
    edges: dict[int, list[int]] = {i: [i + 1] for i in range(length)}
    edges[length] = [0]
    return AccessiblePointedGraph(root=0, edges=edges)


def test_deep_chain_is_acyclic_without_exhausting_the_python_stack() -> None:
    assert _chain(DEEP).has_cycles() is False


def test_deep_cycle_is_detected_without_exhausting_the_python_stack() -> None:
    assert _cycle(DEEP).has_cycles() is True


def test_deep_chain_sorts_topologically() -> None:
    order = _chain(DEEP).topological_sort()
    assert len(order) == DEEP + 1
    # The chain admits exactly one topological order, root first.
    assert order[0] == Node(0)
    assert order[-1] == Node(DEEP)
    position = {node: i for i, node in enumerate(order)}
    graph = _chain(DEEP)
    for node in graph.nodes:
        for child in graph.children(node):
            assert position[node] < position[child]


def test_deep_cycle_refuses_to_sort_rather_than_crashing() -> None:
    with pytest.raises(ValueError, match="cycles"):
        _cycle(DEEP).topological_sort()


def test_deep_chain_condenses_without_exhausting_the_python_stack() -> None:
    condensed = scc_quotient(_chain(DEEP))
    # Nothing to contract in a chain: every node is its own component.
    assert len(condensed.nodes) == DEEP + 1
    assert condensed.has_cycles() is False


def test_deep_cycle_condenses_to_a_single_point() -> None:
    condensed = scc_quotient(_cycle(DEEP))
    assert len(condensed.nodes) == 1
    assert condensed.has_cycles() is False


def test_deep_chain_bisimulation_quotient_is_the_chain_itself() -> None:
    # No two distinct nodes of a chain are bisimilar -- they sit at different
    # distances from the well-founded end -- so the quotient cannot collapse it.
    quotient = _chain(BISIM_DEEP).bisimulation_quotient()
    assert len(quotient.nodes) == BISIM_DEEP + 1


def test_deep_cycle_bisimulation_quotient_is_a_single_self_loop() -> None:
    # Every node of a pure loop has the same unfolding, the canonical Omega.
    quotient = _cycle(BISIM_DEEP).bisimulation_quotient()
    assert len(quotient.nodes) == 1
    root = next(iter(quotient.nodes))
    assert quotient.children(root) == {root}


def test_deep_refinement_agrees_with_the_quotient() -> None:
    graph = _cycle(BISIM_DEEP)
    partition = refine_to_bisimulation(graph)
    assert len(partition) == 1


@pytest.mark.parametrize("length", [1, 2, 10, 1200, DEEP])
def test_condensation_is_acyclic_at_every_depth(length: int) -> None:
    for graph in (_chain(length), _cycle(length)):
        assert scc_quotient(graph).has_cycles() is False
