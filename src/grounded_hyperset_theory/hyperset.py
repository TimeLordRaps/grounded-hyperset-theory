"""Hyperset definitions, bisimulation equivalence, and constructive membership."""

from __future__ import annotations

from typing import Any, Hashable, Iterable, Mapping

from .graph import AccessiblePointedGraph, Node


def bisimilar(g1: AccessiblePointedGraph, g2: AccessiblePointedGraph) -> bool:
    """Determine whether two Accessible Pointed Graphs are bisimilar.

    Under Aczel's Anti-Foundation Axiom (AFA), two hypersets are identical
    if and only if their underlying APGs are bisimilar.
    """
    # Candidate bisimulation relation initialized to Cartesian product of nodes
    # We refine by iteratively eliminating pairs (u, v) that fail the forward or backward condition.
    nodes1 = list(g1.nodes)
    nodes2 = list(g2.nodes)

    # R is a set of valid pairs (u, v)
    r_set: set[tuple[Node, Node]] = {(u, v) for u in nodes1 for v in nodes2}

    changed = True
    while changed:
        changed = False
        to_remove: set[tuple[Node, Node]] = set()

        for u, v in r_set:
            u_children = g1.children(u)
            v_children = g2.children(v)

            # Condition 1: For each u' in children(u), exists v' in children(v) with (u', v') in R
            fwd_ok = all(
                any((u_prime, v_prime) in r_set for v_prime in v_children)
                for u_prime in u_children
            )

            # Condition 2: For each v' in children(v), exists u' in children(u) with (u', v') in R
            bwd_ok = all(
                any((u_prime, v_prime) in r_set for u_prime in u_children)
                for v_prime in v_children
            )

            if not (fwd_ok and bwd_ok):
                to_remove.add((u, v))

        if to_remove:
            r_set -= to_remove
            changed = True

    return (g1.root, g2.root) in r_set


class Hyperset:
    """A non-well-founded set represented by an Accessible Pointed Graph."""

    def __init__(
        self,
        apg: AccessiblePointedGraph | None = None,
        *,
        root: Node | Hashable | None = None,
        edges: Mapping[Node | Hashable, Iterable[Node | Hashable]] | None = None,
    ) -> None:
        if apg is not None:
            self.apg = apg
        elif root is not None and edges is not None:
            self.apg = AccessiblePointedGraph(root=root, edges=edges)
        else:
            # Default to empty set
            r = Node(0, label="∅")
            self.apg = AccessiblePointedGraph(root=r, edges={r: ()})

    @classmethod
    def from_elements(cls, *elements: Hyperset) -> Hyperset:
        """Construct a hyperset containing the given member hypersets."""
        if not elements:
            return EmptyHyperset()
        root = Node("root_set")
        edges: dict[Node, set[Node]] = {root: set()}
        for i, elem in enumerate(elements):
            elem_root = elem.apg.root
            mapped_root = Node((i, elem_root.id), label=elem_root.label)
            edges[root].add(mapped_root)
            for n in elem.apg.nodes:
                mapped_n = Node((i, n.id), label=n.label)
                if mapped_n not in edges:
                    edges[mapped_n] = set()
                for c in elem.apg.children(n):
                    mapped_c = Node((i, c.id), label=c.label)
                    edges[mapped_n].add(mapped_c)
        return cls(AccessiblePointedGraph(root=root, edges=edges))

    @property
    def is_well_founded(self) -> bool:
        """Return True if the set has no circular self-memberships or cycles."""
        return not self.apg.has_cycles()

    @property
    def is_empty(self) -> bool:
        """Return True if this is the empty set ∅."""
        return len(self.apg.children(self.apg.root)) == 0

    def cardinality(self) -> int:
        """Return the number of distinct member hypersets under bisimulation equivalence."""
        distinct: list[Hyperset] = []
        for m in self.members():
            if not any(bisimilar(m.apg, d.apg) for d in distinct):
                distinct.append(m)
        return len(distinct)

    def __len__(self) -> int:
        return self.cardinality()

    def members(self) -> list[Hyperset]:
        """Return the immediate member hypersets of this set."""
        result: list[Hyperset] = []
        for child in self.apg.children(self.apg.root):
            sub_apg = self.apg.subgraph_from(child)
            result.append(Hyperset(sub_apg))
        return result

    def contains(self, item: Hyperset) -> bool:
        """Return True if item is constructively a member of this hyperset."""
        for child in self.apg.children(self.apg.root):
            child_apg = self.apg.subgraph_from(child)
            if bisimilar(child_apg, item.apg):
                return True
        return False

    def union(self, other: Hyperset) -> Hyperset:
        """Return the set-theoretic union self ∪ other."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"union requires Hyperset, got {type(other).__name__}")
        all_members = self.members() + other.members()
        return Hyperset.from_elements(*all_members)

    def __or__(self, other: Any) -> Hyperset:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return self.union(other)

    def intersection(self, other: Hyperset) -> Hyperset:
        """Return the set-theoretic intersection self ∩ other."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"intersection requires Hyperset, got {type(other).__name__}")
        common = [m for m in self.members() if m in other]
        return Hyperset.from_elements(*common)

    def __and__(self, other: Any) -> Hyperset:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return self.intersection(other)

    def difference(self, other: Hyperset) -> Hyperset:
        """Return the set difference self \\ other."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"difference requires Hyperset, got {type(other).__name__}")
        remaining = [m for m in self.members() if m not in other]
        return Hyperset.from_elements(*remaining)

    def __sub__(self, other: Any) -> Hyperset:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return self.difference(other)

    def is_subset(self, other: Hyperset) -> bool:
        """Return True if self is a subset of other (self ⊆ other)."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"is_subset requires Hyperset, got {type(other).__name__}")
        return all(m in other for m in self.members())

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return self.is_subset(other)

    def is_proper_subset(self, other: Hyperset) -> bool:
        """Return True if self is a proper subset of other (self ⊂ other)."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"is_proper_subset requires Hyperset, got {type(other).__name__}")
        return self.is_subset(other) and self != other

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return self.is_proper_subset(other)

    def is_superset(self, other: Hyperset) -> bool:
        """Return True if self is a superset of other (self ⊇ other)."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"is_superset requires Hyperset, got {type(other).__name__}")
        return other.is_subset(self)

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return self.is_superset(other)

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Hyperset):
            return NotImplemented
        return other.is_proper_subset(self)

    def successor(self) -> Hyperset:
        """Return the von Neumann successor S(x) = x ∪ {x}."""
        return self.union(Hyperset.from_elements(self))

    def canonical(self) -> Hyperset:
        """Return the canonical strongly extensional hyperset via bisimulation quotient."""
        return Hyperset(self.apg.bisimulation_quotient())

    def is_transitive(self) -> bool:
        """Return True if every element of self is also a subset of self."""
        return all(m.is_subset(self) for m in self.members())

    def is_ordinal(self) -> bool:
        """Return True if self is a von Neumann ordinal.

        An ordinal is a well-founded transitive set whose members are strictly
        linearly ordered by the membership relation.
        """
        if not self.is_well_founded or not self.is_transitive():
            return False
        m_list: list[Hyperset] = []
        for m in self.members():
            if not any(m == d for d in m_list):
                m_list.append(m)
        for i, a in enumerate(m_list):
            for b in m_list[i + 1:]:
                if not (a in b or b in a or a == b):
                    return False
        return True

    def powerset(self) -> Hyperset:
        """Return the power set P(self), containing all subsets of self."""
        distinct_m: list[Hyperset] = []
        for m in self.members():
            if not any(m == d for d in distinct_m):
                distinct_m.append(m)
        n = len(distinct_m)
        subsets: list[Hyperset] = []
        for i in range(1 << n):
            subset_elements = [distinct_m[j] for j in range(n) if (i >> j) & 1]
            subsets.append(Hyperset.from_elements(*subset_elements))
        return Hyperset.from_elements(*subsets)

    def big_union(self) -> Hyperset:
        """Return the generalized union ⋃ self = {x : ∃ y ∈ self, x ∈ y}."""
        elements = [elem for m in self.members() for elem in m.members()]
        return Hyperset.from_elements(*elements)

    def big_intersection(self) -> Hyperset:
        """Return the generalized intersection ⋂ self = {x : ∀ y ∈ self, x ∈ y}."""
        members = self.members()
        if not members:
            raise ValueError("big_intersection of the empty set is undefined in set theory")
        res = members[0]
        for m in members[1:]:
            res = res.intersection(m)
        return res

    def cartesian_product(self, other: Hyperset) -> Hyperset:
        """Return the Cartesian product self × other = {(a, b) : a ∈ self, b ∈ other}."""
        if not isinstance(other, Hyperset):
            raise TypeError(f"cartesian_product requires Hyperset, got {type(other).__name__}")
        pairs = [pair(a, b) for a in self.members() for b in other.members()]
        return Hyperset.from_elements(*pairs)

    def transitive_closure(self) -> Hyperset:
        """Return the transitive closure TC(self), the smallest transitive set containing self."""
        initial = set(self.apg.children(self.apg.root))
        if not initial:
            return EmptyHyperset()
        from collections import deque
        visited: set[Node] = set()
        queue: deque[Node] = deque(initial)
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                for child in self.apg.children(curr):
                    if child not in visited:
                        queue.append(child)
        return Hyperset.from_elements(*(Hyperset(self.apg.subgraph_from(d)) for d in visited))

    def to_int(self) -> int:
        """Return the exact integer value if self is a finite von Neumann ordinal."""
        if not self.is_well_founded:
            raise ValueError("Cannot convert non-well-founded hyperset to integer")
        if not self.is_ordinal():
            raise ValueError("Hyperset is not a von Neumann ordinal")
        return len(self)

    def __int__(self) -> int:
        return self.to_int()

    def canonical_signature(self) -> tuple[Hashable, tuple[tuple[Hashable, tuple[Hashable, ...]], ...]]:
        """Return the canonical structural signature of this hyperset under bisimulation."""
        return self.apg.canonical_signature()

    def __hash__(self) -> int:
        if not hasattr(self, "_hash_cache"):
            object.__setattr__(self, "_hash_cache", hash(self.canonical_signature()))
        return self._hash_cache

    def __contains__(self, item: Any) -> bool:
        if not isinstance(item, Hyperset):
            return False
        return self.contains(item)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Hyperset):
            return False
        if hash(self) != hash(other):
            return False
        return bisimilar(self.apg, other.apg)

    def __repr__(self) -> str:
        if not self.apg.children(self.apg.root):
            return "Hyperset(∅)"
        if self.apg.has_cycles():
            if self.contains(self):
                return "Hyperset(Ω = {Ω})"
            return f"Hyperset(cyclic: root={self.apg.root})"
        return f"Hyperset(root={self.apg.root}, elements={len(self.apg.children(self.apg.root))})"


def EmptyHyperset() -> Hyperset:
    """The empty set ∅."""
    r = Node(0, label="∅")
    return Hyperset(AccessiblePointedGraph(root=r, edges={r: ()}))


def QuineAtom() -> Hyperset:
    """The canonical Quine atom Ω = {Ω}, satisfying Ω ∈ Ω."""
    omega = Node("Ω", label="Ω")
    return Hyperset(AccessiblePointedGraph(root=omega, edges={omega: [omega]}))


def pair(a: Hyperset, b: Hyperset) -> Hyperset:
    """Construct the Kuratowski ordered pair (a, b) = {{a}, {a, b}}."""
    if not isinstance(a, Hyperset) or not isinstance(b, Hyperset):
        raise TypeError("pair requires two Hyperset arguments")
    return Hyperset.from_elements(
        Hyperset.from_elements(a),
        Hyperset.from_elements(a, b),
    )


def von_neumann_ordinal(n: int) -> Hyperset:
    """Construct the nth von Neumann ordinal: 0 = ∅, n+1 = S(n) = n ∪ {n}.

    Constructs the canonical transitively closed DAG directly in O(n^2) time with
    n + 1 nodes, avoiding O(2^n) exponential node replication.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"Ordinal index must be an exact integer, got {type(n).__name__}")
    if n < 0:
        raise ValueError(f"Ordinal index must be non-negative, got {n}")
    if n == 0:
        return EmptyHyperset()

    nodes = [Node(i, label=str(i)) for i in range(n + 1)]
    edges = {nodes[i]: [nodes[j] for j in range(i)] for i in range(n + 1)}
    return Hyperset(AccessiblePointedGraph(root=nodes[n], edges=edges))


def solve_system(equations: Mapping[Hashable, Iterable[Hashable]]) -> dict[Hashable, Hyperset]:
    """Solve a system of set equations under Aczel's Anti-Foundation Axiom (AFA).

    For example: `solve_system({"x": ["y"], "y": ["x"]})` returns the unique hypersets
    for variables 'x' and 'y' (both equal to the Quine atom Ω).
    """
    raw_edges: dict[Node, set[Node]] = {}
    for var, children in equations.items():
        v_node = Node(var)
        c_nodes = {Node(c) for c in children}
        raw_edges[v_node] = c_nodes

    # Ensure all referenced children have an entry in raw_edges
    for c_set in list(raw_edges.values()):
        for c in c_set:
            if c not in raw_edges:
                raw_edges[c] = set()

    results: dict[Hashable, Hyperset] = {}
    for var in equations:
        apg = AccessiblePointedGraph(root=var, edges=raw_edges)
        results[var] = Hyperset(apg)
    return results


def ordinal_add(alpha: Hyperset, beta: Hyperset) -> Hyperset:
    """Ordinal addition for finite von Neumann ordinals: alpha + beta."""
    if not isinstance(alpha, Hyperset) or not isinstance(beta, Hyperset):
        raise TypeError("ordinal_add requires Hyperset arguments")
    return von_neumann_ordinal(alpha.to_int() + beta.to_int())


def ordinal_mul(alpha: Hyperset, beta: Hyperset) -> Hyperset:
    """Ordinal multiplication for finite von Neumann ordinals: alpha * beta."""
    if not isinstance(alpha, Hyperset) or not isinstance(beta, Hyperset):
        raise TypeError("ordinal_mul requires Hyperset arguments")
    return von_neumann_ordinal(alpha.to_int() * beta.to_int())


def ordinal_pow(alpha: Hyperset, exponent: int | Hyperset) -> Hyperset:
    """Ordinal exponentiation for finite von Neumann ordinals: alpha ** exponent."""
    if not isinstance(alpha, Hyperset):
        raise TypeError("ordinal_pow requires Hyperset base")
    exp = exponent.to_int() if isinstance(exponent, Hyperset) else exponent
    if not isinstance(exp, int) or isinstance(exp, bool):
        raise TypeError("exponent must be an exact integer or ordinal Hyperset")
    if exp < 0:
        raise ValueError("ordinal exponent must be non-negative")
    return von_neumann_ordinal(alpha.to_int() ** exp)
