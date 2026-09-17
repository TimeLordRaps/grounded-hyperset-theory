"""Regression tests for Accessible Pointed Graphs (APGs)."""

from __future__ import annotations

from grounded_hyperset_theory.graph import AccessiblePointedGraph, Node


def test_accessible_nodes_pruning():
    # Node 3 is disconnected and unreachable from root 0
    edges = {
        0: [1, 2],
        1: [2],
        2: [],
        3: [1],
    }
    apg = AccessiblePointedGraph(root=0, edges=edges)
    node_ids = {n.id for n in apg.nodes}
    assert node_ids == {0, 1, 2}
    assert Node(3) not in apg.nodes


def test_cycle_detection():
    # Acyclic graph
    edges_acyclic = {
        0: [1, 2],
        1: [2],
        2: [],
    }
    apg_acyclic = AccessiblePointedGraph(root=0, edges=edges_acyclic)
    assert not apg_acyclic.has_cycles()

    # Cyclic graph (self-loop)
    edges_self_loop = {0: [0]}
    apg_self = AccessiblePointedGraph(root=0, edges=edges_self_loop)
    assert apg_self.has_cycles()

    # Cyclic graph (2-cycle)
    edges_cycle = {0: [1], 1: [0]}
    apg_cycle = AccessiblePointedGraph(root=0, edges=edges_cycle)
    assert apg_cycle.has_cycles()


def test_subgraph_from():
    edges = {
        "root": ["child1", "child2"],
        "child1": ["leaf1"],
        "child2": ["leaf2"],
        "leaf1": [],
        "leaf2": [],
    }
    apg = AccessiblePointedGraph(root="root", edges=edges)
    sub = apg.subgraph_from("child1")
    assert sub.root == Node("child1")
    assert {n.id for n in sub.nodes} == {"child1", "leaf1"}


def test_topological_sort():
    edges = {
        0: [1, 2],
        1: [3],
        2: [3],
        3: [],
    }
    apg = AccessiblePointedGraph(root=0, edges=edges)
    order = apg.topological_sort()
    assert order[0] == Node(0)
    assert order[-1] == Node(3)
    assert len(order) == 4


def test_topological_sort_cycle_error():
    import pytest
    edges = {0: [1], 1: [0]}
    apg = AccessiblePointedGraph(root=0, edges=edges)
    with pytest.raises(ValueError, match="Cannot topologically sort"):
        apg.topological_sort()


def test_properties_and_errors():
    import pytest
    empty_apg = AccessiblePointedGraph(root=0, edges={0: []})
    assert empty_apg.is_empty
    assert empty_apg.edge_count == 0

    apg = AccessiblePointedGraph(root=0, edges={0: [1], 1: []})
    assert not apg.is_empty
    assert apg.edge_count == 1
    assert apg.children(0) == {Node(1)}

    with pytest.raises(KeyError):
        apg.children("missing")
    with pytest.raises(KeyError):
        apg.subgraph_from("missing")


def test_bisimulation_quotient_collapses_2cycle():
    # 2-cycle a -> b -> a should collapse to single vertex with self loop
    a = Node("a")
    b = Node("b")
    apg_2cycle = AccessiblePointedGraph(root=a, edges={a: [b], b: [a]})
    assert len(apg_2cycle.nodes) == 2

    quotient = apg_2cycle.bisimulation_quotient()
    assert len(quotient.nodes) == 1
    q_root = quotient.root
    assert quotient.children(q_root) == {q_root}
    assert quotient.has_cycles()


def test_bisimulation_quotient_redundant_leaves():
    # root -> leaf1, root -> leaf2, both leaves have no children
    # Quotient should merge leaf1 and leaf2 into a single empty set node
    r = Node("r")
    l1 = Node("l1")
    l2 = Node("l2")
    apg = AccessiblePointedGraph(root=r, edges={r: [l1, l2], l1: [], l2: []})
    assert len(apg.nodes) == 3

    quotient = apg.bisimulation_quotient()
    assert len(quotient.nodes) == 2
    assert len(quotient.children(quotient.root)) == 1
