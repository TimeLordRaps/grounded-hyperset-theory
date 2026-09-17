"""Accessible Pointed Graphs (APGs) for modeling hyperset topologies."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Hashable, Iterable, Mapping, Set


@dataclass(frozen=True)
class Node:
    """A discrete vertex in an Accessible Pointed Graph."""
    id: Hashable
    label: str | None = None

    def __str__(self) -> str:
        return self.label if self.label is not None else str(self.id)


class AccessiblePointedGraph:
    """An Accessible Pointed Graph (APG): a directed graph (G, r) where all nodes are reachable from r."""

    def __init__(
        self,
        root: Node | Hashable,
        edges: Mapping[Node | Hashable, Iterable[Node | Hashable]],
    ) -> None:
        self.root = root if isinstance(root, Node) else Node(root)

        # Canonicalize raw nodes and edges into Node objects
        raw_edges: dict[Node, set[Node]] = {}
        for parent, children in edges.items():
            p_node = parent if isinstance(parent, Node) else Node(parent)
            c_nodes = {c if isinstance(c, Node) else Node(c) for c in children}
            raw_edges[p_node] = c_nodes

        # Ensure all referenced children have an entry
        for c_set in list(raw_edges.values()):
            for c in c_set:
                if c not in raw_edges:
                    raw_edges[c] = set()

        if self.root not in raw_edges:
            raw_edges[self.root] = set()

        # Compute accessible subgraph from root (BFS reachability)
        reachable: set[Node] = set()
        queue: deque[Node] = deque([self.root])
        while queue:
            curr = queue.popleft()
            if curr not in reachable:
                reachable.add(curr)
                for child in raw_edges.get(curr, ()):
                    if child not in reachable:
                        queue.append(child)

        self._nodes = frozenset(reachable)
        self._edges: dict[Node, frozenset[Node]] = {
            n: frozenset(raw_edges.get(n, set()) & self._nodes)
            for n in self._nodes
        }

    @property
    def nodes(self) -> Set[Node]:
        """All nodes accessible from the root."""
        return self._nodes

    @property
    def edge_count(self) -> int:
        """Total number of directed edges in the accessible graph."""
        return sum(len(c) for c in self._edges.values())

    @property
    def is_empty(self) -> bool:
        """Return True if the root has no outgoing edges (represents empty set ∅)."""
        return len(self._edges.get(self.root, ())) == 0

    def children(self, node: Node | Hashable) -> Set[Node]:
        """Return children of the specified node."""
        n = node if isinstance(node, Node) else Node(node)
        if n not in self._edges:
            raise KeyError(f"Node {n} is not in this APG.")
        return self._edges[n]

    def has_cycles(self) -> bool:
        """Return True if the accessible graph contains any directed cycles."""
        visited: set[Node] = set()
        rec_stack: set[Node] = set()

        def dfs(curr: Node) -> bool:
            visited.add(curr)
            rec_stack.add(curr)
            for neighbor in self._edges.get(curr, ()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(curr)
            return False

        return dfs(self.root)

    def topological_sort(self) -> list[Node]:
        """Return a topological sort of nodes if acyclic.

        Raises ValueError if the graph contains any cycle.
        """
        if self.has_cycles():
            raise ValueError("Cannot topologically sort a graph with cycles.")
        visited: set[Node] = set()
        order: list[Node] = []

        def dfs(curr: Node) -> None:
            visited.add(curr)
            for child in sorted(self._edges.get(curr, ()), key=lambda x: str(x.id)):
                if child not in visited:
                    dfs(child)
            order.append(curr)

        dfs(self.root)
        return order[::-1]

    def subgraph_from(self, new_root: Node | Hashable) -> AccessiblePointedGraph:
        """Derive the accessible pointed subgraph rooted at new_root."""
        n = new_root if isinstance(new_root, Node) else Node(new_root)
        if n not in self._nodes:
            raise KeyError(f"Node {n} is not in this APG.")
        return AccessiblePointedGraph(root=n, edges=self._edges)

    def bisimulation_quotient(self) -> AccessiblePointedGraph:
        """Compute the canonical strongly extensional bisimulation quotient APG.

        Under Aczel's AFA, merges all mutually bisimilar nodes within this APG
        into unique equivalence classes, producing the minimal canonical representation.
        """
        nodes = list(self._nodes)
        # Initial partition: map each node to an initial block 0
        node_to_block: dict[Node, int] = {n: 0 for n in nodes}

        changed = True
        while changed:
            # Compute signature for each node: frozenset of child block ids
            signatures: dict[Node, frozenset[int]] = {
                n: frozenset(node_to_block[c] for c in self._edges.get(n, ()))
                for n in nodes
            }
            # Group by signature
            sig_to_nodes: dict[tuple[int, frozenset[int]], list[Node]] = {}
            for n in nodes:
                key = (node_to_block[n], signatures[n])
                sig_to_nodes.setdefault(key, []).append(n)

            # Assign new block indices sorted purely structurally
            new_node_to_block: dict[Node, int] = {}
            block_counter = 0
            sorted_keys = sorted(sig_to_nodes.keys(), key=lambda k: (k[0], len(k[1]), tuple(sorted(k[1]))))
            for key in sorted_keys:
                for n in sig_to_nodes[key]:
                    new_node_to_block[n] = block_counter
                block_counter += 1

            if len(set(new_node_to_block.values())) == len(set(node_to_block.values())):
                # Partition has stabilized
                node_to_block = new_node_to_block
                changed = False
            else:
                node_to_block = new_node_to_block

        # Build canonical quotient graph with deterministic integer node IDs
        root_block = node_to_block[self.root]
        canonical_map: dict[int, Node] = {root_block: Node(0)}
        queue: deque[int] = deque([root_block])
        next_id = 1

        # Map block -> set of child blocks
        block_children: dict[int, set[int]] = {}
        for n in nodes:
            b = node_to_block[n]
            if b not in block_children:
                block_children[b] = set()
            for c in self._edges.get(n, ()):
                block_children[b].add(node_to_block[c])

        while queue:
            curr_b = queue.popleft()
            for child_b in sorted(block_children.get(curr_b, set())):
                if child_b not in canonical_map:
                    canonical_map[child_b] = Node(next_id)
                    next_id += 1
                    queue.append(child_b)

        quotient_root = canonical_map[root_block]
        quotient_edges: dict[Node, set[Node]] = {
            canonical_map[b]: {canonical_map[c] for c in block_children.get(b, set())}
            for b in canonical_map
        }

        return AccessiblePointedGraph(root=quotient_root, edges=quotient_edges)

    def canonical_signature(self) -> tuple[Hashable, tuple[tuple[Hashable, tuple[Hashable, ...]], ...]]:
        """Return an immutable structural signature of this APG.

        Two APGs have the same signature under bisimulation quotient if and only if
        they are bisimilar under Aczel's AFA.
        """
        quotient = self.bisimulation_quotient()
        edges_tuple = tuple(
            sorted(
                (n.id, tuple(sorted(c.id for c in quotient._edges.get(n, ()))))
                for n in quotient._nodes
            )
        )
        return (quotient.root.id, edges_tuple)

    def __repr__(self) -> str:
        return f"AccessiblePointedGraph(root={self.root}, nodes={len(self._nodes)}, edges={self.edge_count})"
