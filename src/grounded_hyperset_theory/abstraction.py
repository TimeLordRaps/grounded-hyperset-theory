"""Abstraction mappings, congruences, and quotienting on APGs and Hypersets."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Hashable, Iterable, Mapping, Set

from .graph import AccessiblePointedGraph, Node
from .hyperset import Hyperset


class NodePartition:
    """An equivalence relation on vertices of an Accessible Pointed Graph.

    Partitions a set of nodes into mutually disjoint equivalence blocks.
    """

    def __init__(self, node_to_block: Mapping[Node, Hashable]) -> None:
        self._node_to_block: dict[Node, Hashable] = dict(node_to_block)
        self._block_to_nodes: dict[Hashable, set[Node]] = {}
        for n, b in self._node_to_block.items():
            self._block_to_nodes.setdefault(b, set()).add(n)

    @classmethod
    def from_mapping(cls, mapping: Mapping[Node | Hashable, Hashable]) -> NodePartition:
        """Construct a partition from a mapping from node (or node id) to block id."""
        node_map: dict[Node, Hashable] = {}
        for k, v in mapping.items():
            n = k if isinstance(k, Node) else Node(k)
            node_map[n] = v
        return cls(node_map)

    @classmethod
    def from_blocks(cls, blocks: Iterable[Iterable[Node | Hashable]]) -> NodePartition:
        """Construct a partition from an iterable of equivalence blocks."""
        node_map: dict[Node, Hashable] = {}
        for block_id, block in enumerate(blocks):
            for item in block:
                n = item if isinstance(item, Node) else Node(item)
                node_map[n] = block_id
        return cls(node_map)

    @classmethod
    def from_relation(
        cls,
        nodes: Iterable[Node | Hashable],
        relation: Callable[[Node, Node], bool],
    ) -> NodePartition:
        """Construct an equivalence partition from a reflexive/symmetric/transitive relation."""
        node_list = [n if isinstance(n, Node) else Node(n) for n in nodes]
        node_map: dict[Node, Hashable] = {}
        blocks: list[set[Node]] = []

        for u in node_list:
            matched = False
            for b_idx, block in enumerate(blocks):
                rep = next(iter(block))
                if relation(u, rep):
                    block.add(u)
                    node_map[u] = b_idx
                    matched = True
                    break
            if not matched:
                new_idx = len(blocks)
                blocks.append({u})
                node_map[u] = new_idx

        return cls(node_map)

    def block_of(self, node: Node | Hashable) -> Hashable:
        """Return the block identifier for the given node."""
        n = node if isinstance(node, Node) else Node(node)
        if n not in self._node_to_block:
            raise KeyError(f"Node {n} is not in this partition.")
        return self._node_to_block[n]

    def block_members(self, block_id: Hashable) -> Set[Node]:
        """Return all nodes in the given block."""
        return frozenset(self._block_to_nodes.get(block_id, set()))

    def blocks(self) -> list[set[Node]]:
        """Return all equivalence blocks in this partition."""
        return [set(s) for s in self._block_to_nodes.values()]

    def block_ids(self) -> set[Hashable]:
        """Return all block identifiers."""
        return set(self._block_to_nodes.keys())

    def nodes(self) -> Set[Node]:
        """Return all partitioned nodes."""
        return frozenset(self._node_to_block.keys())

    def is_equivalent(self, u: Node | Hashable, v: Node | Hashable) -> bool:
        """Return True if u and v belong to the same equivalence block."""
        return self.block_of(u) == self.block_of(v)

    def refine(self, finer: NodePartition) -> NodePartition:
        """Compute the meet (infimum) of two partitions: u ~ v iff u ~_self v and u ~_finer v."""
        common_nodes = set(self._node_to_block.keys()) & set(finer._node_to_block.keys())
        combined_map: dict[Node, Hashable] = {
            n: (self._node_to_block[n], finer._node_to_block[n])
            for n in common_nodes
        }
        return NodePartition(combined_map)

    def __len__(self) -> int:
        return len(self._block_to_nodes)

    def __repr__(self) -> str:
        return f"NodePartition(blocks={len(self._block_to_nodes)}, nodes={len(self._node_to_block)})"


@dataclass(frozen=True)
class AbstractionMapping:
    """A Galois connection abstraction mapping between concrete and abstract states."""

    abstract_fn: Callable[[Node], Hashable]
    name: str = "abstraction"

    def abstract(self, node: Node) -> Hashable:
        """Map concrete node to abstract identifier."""
        return self.abstract_fn(node)

    def to_partition(self, nodes: Iterable[Node]) -> NodePartition:
        """Create a partition of nodes induced by this abstraction mapping."""
        mapping = {n: self.abstract_fn(n) for n in nodes}
        return NodePartition(mapping)


def quotient_apg(
    apg: AccessiblePointedGraph,
    partition: NodePartition | Mapping[Node | Hashable, Hashable],
) -> AccessiblePointedGraph:
    """Construct the quotient Accessible Pointed Graph G / ~ under an equivalence partition.

    Vertices of the quotient graph are the equivalence blocks of the partition.
    An edge [u] -> [v] exists in G / ~ if there exists u' in [u] and v' in [v] such that u' -> v'.
    Prunes unreachable blocks from the quotient root [root].
    """
    if not isinstance(partition, NodePartition):
        partition = NodePartition.from_mapping(partition)

    # Ensure all nodes in apg have a block; assign unassigned nodes to singleton blocks
    node_to_block: dict[Node, Hashable] = {}
    for n in apg.nodes:
        if n in partition._node_to_block:
            node_to_block[n] = partition._node_to_block[n]
        else:
            node_to_block[n] = n.id

    root_block = node_to_block[apg.root]

    # Map block ids to canonical integer Node IDs
    block_nodes: dict[Hashable, Node] = {root_block: Node(0, label=str(root_block))}
    queue: deque[Hashable] = deque([root_block])
    next_id = 1

    # Raw block edges
    raw_block_edges: dict[Hashable, set[Hashable]] = {}
    for u in apg.nodes:
        b_u = node_to_block[u]
        raw_block_edges.setdefault(b_u, set())
        for v in apg.children(u):
            b_v = node_to_block[v]
            raw_block_edges[b_u].add(b_v)

    while queue:
        curr_b = queue.popleft()
        for child_b in sorted(raw_block_edges.get(curr_b, set()), key=str):
            if child_b not in block_nodes:
                block_nodes[child_b] = Node(next_id, label=str(child_b))
                next_id += 1
                queue.append(child_b)

    quotient_edges: dict[Node, set[Node]] = {}
    for b_id, q_node in block_nodes.items():
        children = {
            block_nodes[child_b]
            for child_b in raw_block_edges.get(b_id, set())
            if child_b in block_nodes
        }
        quotient_edges[q_node] = children

    return AccessiblePointedGraph(root=block_nodes[root_block], edges=quotient_edges)


def quotient_hyperset(
    hyperset: Hyperset,
    partition: NodePartition | Mapping[Node | Hashable, Hashable],
) -> Hyperset:
    """Construct the quotient Hyperset of a given hyperset under an equivalence partition."""
    return Hyperset(quotient_apg(hyperset.apg, partition))


def is_congruence(
    apg: AccessiblePointedGraph,
    partition: NodePartition | Mapping[Node | Hashable, Hashable],
) -> bool:
    """Check if a partition is a forward simulation congruence on an APG.

    For all u ~ v, for every child u' of u, there exists a child v' of v such that u' ~ v'.
    """
    if not isinstance(partition, NodePartition):
        partition = NodePartition.from_mapping(partition)

    for block in partition.blocks():
        block_nodes = [n for n in block if n in apg.nodes]
        if len(block_nodes) <= 1:
            continue
        for u in block_nodes:
            u_children = apg.children(u)
            for v in block_nodes:
                if u == v:
                    continue
                v_children = apg.children(v)
                # Every child of u must have a corresponding child of v in the same block
                for u_prime in u_children:
                    u_prime_block = partition.block_of(u_prime)
                    if not any(partition.block_of(v_prime) == u_prime_block for v_prime in v_children):
                        return False
    return True


def is_bisimulation_congruence(
    apg: AccessiblePointedGraph,
    partition: NodePartition | Mapping[Node | Hashable, Hashable],
) -> bool:
    """Check if an equivalence partition satisfies the full bisimulation conditions on an APG."""
    if not isinstance(partition, NodePartition):
        partition = NodePartition.from_mapping(partition)

    for block in partition.blocks():
        block_nodes = [n for n in block if n in apg.nodes]
        if len(block_nodes) <= 1:
            continue
        for i, u in enumerate(block_nodes):
            u_children = apg.children(u)
            for v in block_nodes[i + 1:]:
                v_children = apg.children(v)

                # Forward: u' in children(u) => exists v' in children(v) with u' ~ v'
                for u_prime in u_children:
                    u_block = partition.block_of(u_prime)
                    if not any(partition.block_of(v_prime) == u_block for v_prime in v_children):
                        return False

                # Backward: v' in children(v) => exists u' in children(u) with u' ~ v'
                for v_prime in v_children:
                    v_block = partition.block_of(v_prime)
                    if not any(partition.block_of(u_prime) == v_block for u_prime in u_children):
                        return False
    return True


def refine_to_bisimulation(
    apg: AccessiblePointedGraph,
    initial_partition: NodePartition | Mapping[Node | Hashable, Hashable] | None = None,
) -> NodePartition:
    """Refine a partition to the coarsest bisimulation compatible with initial_partition.

    If initial_partition is None, computes the coarsest bisimulation over all nodes.
    """
    nodes = list(apg.nodes)
    if initial_partition is None:
        node_to_block: dict[Node, Hashable] = {n: 0 for n in nodes}
    elif isinstance(initial_partition, NodePartition):
        node_to_block = {n: initial_partition.block_of(n) for n in nodes if n in initial_partition._node_to_block}
        for n in nodes:
            if n not in node_to_block:
                node_to_block[n] = 0
    else:
        node_to_block = {
            n: initial_partition.get(n, initial_partition.get(n.id, 0))
            for n in nodes
        }

    changed = True
    while changed:
        signatures: dict[Node, frozenset[Hashable]] = {
            n: frozenset(node_to_block[c] for c in apg.children(n))
            for n in nodes
        }
        sig_to_nodes: dict[tuple[Hashable, frozenset[Hashable]], list[Node]] = {}
        for n in nodes:
            key = (node_to_block[n], signatures[n])
            sig_to_nodes.setdefault(key, []).append(n)

        new_node_to_block: dict[Node, Hashable] = {}
        block_counter = 0
        sorted_keys = sorted(
            sig_to_nodes.keys(),
            key=lambda k: (str(k[0]), len(k[1]), tuple(sorted(str(x) for x in k[1]))),
        )
        for key in sorted_keys:
            for n in sig_to_nodes[key]:
                new_node_to_block[n] = block_counter
            block_counter += 1

        if len(set(new_node_to_block.values())) == len(set(node_to_block.values())):
            node_to_block = new_node_to_block
            changed = False
        else:
            node_to_block = new_node_to_block

    return NodePartition(node_to_block)


def depth_abstraction(
    apg: AccessiblePointedGraph,
    max_depth: int,
    truncate_horizon: bool = True,
) -> AccessiblePointedGraph:
    """Compute depth-bounded (k-horizon) abstraction of an APG.

    Nodes at BFS depth >= max_depth are merged into an abstract 'horizon' node.
    If truncate_horizon is True, outgoing transitions beyond the horizon are truncated.
    """
    if max_depth < 0:
        raise ValueError(f"max_depth must be non-negative, got {max_depth}")

    depths: dict[Node, int] = {apg.root: 0}
    queue: deque[Node] = deque([apg.root])
    while queue:
        curr = queue.popleft()
        d = depths[curr]
        for child in apg.children(curr):
            if child not in depths:
                depths[child] = d + 1
                queue.append(child)

    partition_map: dict[Node, Hashable] = {}
    for n in apg.nodes:
        d = depths.get(n, max_depth)
        if d >= max_depth:
            partition_map[n] = "horizon"
        else:
            partition_map[n] = f"depth_{d}_{n.id}"

    q = quotient_apg(apg, partition_map)
    if truncate_horizon:
        horizon_nodes = {n for n in q.nodes if n.label == "horizon"}
        truncated_edges: dict[Node, set[Node]] = {}
        for n in q.nodes:
            if n in horizon_nodes:
                truncated_edges[n] = set()
            else:
                truncated_edges[n] = set(q.children(n))
        return AccessiblePointedGraph(root=q.root, edges=truncated_edges)
    return q


def depth_abstract_hyperset(hyperset: Hyperset, max_depth: int, truncate_horizon: bool = True) -> Hyperset:
    """Depth-abstract a hyperset, truncating or summarizing structure beyond max_depth."""
    return Hyperset(depth_abstraction(hyperset.apg, max_depth, truncate_horizon=truncate_horizon))


def predicate_abstraction(
    apg: AccessiblePointedGraph,
    predicates: Iterable[Callable[[Node], bool]],
) -> AccessiblePointedGraph:
    """Predicate abstraction of an APG: merges nodes satisfying identical truth-value vectors."""
    preds = list(predicates)
    partition_map: dict[Node, tuple[bool, ...]] = {
        n: tuple(bool(p(n)) for p in preds)
        for n in apg.nodes
    }
    return quotient_apg(apg, partition_map)


def predicate_abstract_hyperset(
    hyperset: Hyperset,
    predicates: Iterable[Callable[[Node], bool]],
) -> Hyperset:
    """Predicate-abstract a hyperset using an ensemble of node predicates."""
    return Hyperset(predicate_abstraction(hyperset.apg, predicates))


def scc_quotient(apg: AccessiblePointedGraph) -> AccessiblePointedGraph:
    """Contract Strongly Connected Components (SCCs) to yield an acyclic DAG condensation.

    For non-well-founded hypersets containing cycles, this produces a well-founded
    ZFC-compatible skeleton where every cyclic cluster is contracted into an atomic point.
    Guarantees that the resulting quotient APG has no cycles.
    """
    # Tarjan's SCC algorithm
    index = 0
    indices: dict[Node, int] = {}
    lowlinks: dict[Node, int] = {}
    on_stack: set[Node] = set()
    stack: list[Node] = []
    sccs: list[set[Node]] = []

    def strongconnect(v: Node) -> None:
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in apg.children(v):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: set[Node] = set()
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.add(w)
                if w == v:
                    break
            sccs.append(scc)

    for n in apg.nodes:
        if n not in indices:
            strongconnect(n)

    partition_map: dict[Node, int] = {}
    for scc_id, scc in enumerate(sccs):
        for n in scc:
            partition_map[n] = scc_id

    # The quotient graph might contain self-loops if an SCC had internal edges!
    # To obtain a strictly acyclic condensation DAG, remove self-loops created by contracting SCCs.
    q_apg = quotient_apg(apg, partition_map)
    # Filter out self-loops to ensure strict DAG property
    acyclic_edges: dict[Node, set[Node]] = {
        n: {c for c in q_apg.children(n) if c != n}
        for n in q_apg.nodes
    }
    return AccessiblePointedGraph(root=q_apg.root, edges=acyclic_edges)


def scc_abstract_hyperset(hyperset: Hyperset) -> Hyperset:
    """Abstract a hyperset by collapsing all cyclic SCCs into well-founded points."""
    return Hyperset(scc_quotient(hyperset.apg))
