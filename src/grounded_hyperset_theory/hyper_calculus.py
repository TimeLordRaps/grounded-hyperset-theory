"""Group-theoretic transformations, symmetries, and automorphism groups on APGs and Hypersets."""

from __future__ import annotations

from collections import deque
import math
from typing import Any, Hashable, Iterable, Mapping, Sequence, Set

from .graph import AccessiblePointedGraph, Node
from .hyperset import Hyperset, bisimilar


class Permutation:
    """A bijective permutation on a finite domain of APG nodes or discrete elements."""

    def __init__(self, mapping: Mapping[Node, Node]) -> None:
        self._mapping: dict[Node, Node] = dict(mapping)
        # Verify bijection
        if set(self._mapping.keys()) != set(self._mapping.values()):
            raise ValueError("Permutation mapping must be a bijection on its domain.")
        self._domain = frozenset(self._mapping.keys())

    @property
    def mapping(self) -> dict[Node, Node]:
        """Return a copy of the mapping dictionary."""
        return dict(self._mapping)

    @classmethod
    def identity(cls, domain: Iterable[Node]) -> Permutation:
        """Construct the identity permutation on the given domain."""
        dom = [n if isinstance(n, Node) else Node(n) for n in domain]
        return cls({n: n for n in dom})

    @classmethod
    def from_mapping(cls, mapping: Mapping[Node | Hashable, Node | Hashable]) -> Permutation:
        """Construct a permutation from raw node or hashable key-value pairs."""
        m: dict[Node, Node] = {}
        for k, v in mapping.items():
            kn = k if isinstance(k, Node) else Node(k)
            vn = v if isinstance(v, Node) else Node(v)
            m[kn] = vn
        return cls(m)

    @classmethod
    def from_cycle(cls, cycle: Sequence[Node | Hashable], domain: Iterable[Node | Hashable]) -> Permutation:
        """Construct a single cyclic permutation (c0 -> c1 -> ... -> ck-1 -> c0)."""
        dom = [n if isinstance(n, Node) else Node(n) for n in domain]
        cyc = [n if isinstance(n, Node) else Node(n) for n in cycle]
        mapping: dict[Node, Node] = {n: n for n in dom}
        if len(cyc) > 1:
            for i in range(len(cyc)):
                mapping[cyc[i]] = cyc[(i + 1) % len(cyc)]
        return cls(mapping)

    @property
    def domain(self) -> Set[Node]:
        """All nodes in the domain of this permutation."""
        return self._domain

    def apply(self, node: Node | Hashable) -> Node:
        """Apply the permutation to a node."""
        n = node if isinstance(node, Node) else Node(node)
        return self._mapping.get(n, n)

    def __call__(self, node: Node | Hashable) -> Node:
        return self.apply(node)

    def inverse(self) -> Permutation:
        """Return the inverse permutation p^-1."""
        inv_map = {v: k for k, v in self._mapping.items()}
        return Permutation(inv_map)

    def __invert__(self) -> Permutation:
        return self.inverse()

    def compose(self, other: Permutation) -> Permutation:
        """Return self ∘ other, where (self ∘ other)(x) = self(other(x))."""
        dom = set(self._domain) | set(other._domain)
        comp_map: dict[Node, Node] = {
            n: self.apply(other.apply(n))
            for n in dom
        }
        return Permutation(comp_map)

    def __mul__(self, other: Permutation) -> Permutation:
        return self.compose(other)

    def order(self) -> int:
        """Return the group-theoretic order of this permutation (smallest k >= 1 with p^k = id)."""
        cycles = self.cycles()
        if not cycles:
            return 1
        lengths = [len(c) for c in cycles]
        lcm = lengths[0]
        for length_val in lengths[1:]:
            lcm = (lcm * length_val) // math.gcd(lcm, length_val)
        return lcm

    def cycles(self) -> list[list[Node]]:
        """Decompose this permutation into disjoint cyclic orbits of length > 1."""
        visited: set[Node] = set()
        result: list[list[Node]] = []
        for n in sorted(self._domain, key=lambda x: str(x.id)):
            if n not in visited:
                curr = n
                cycle: list[Node] = []
                while curr not in visited:
                    visited.add(curr)
                    cycle.append(curr)
                    curr = self.apply(curr)
                if len(cycle) > 1:
                    result.append(cycle)
        return result

    @property
    def fixed_points(self) -> Set[Node]:
        """Return all nodes fixed by this permutation."""
        return frozenset(n for n in self._domain if self.apply(n) == n)

    @property
    def is_identity(self) -> bool:
        """Return True if this permutation is the identity on its domain."""
        return all(self.apply(n) == n for n in self._domain)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Permutation):
            return False
        common_domain = set(self._domain) | set(other._domain)
        return all(self.apply(n) == other.apply(n) for n in common_domain)

    def __hash__(self) -> int:
        # Hash non-fixed points so any identity-extended permutations have identical hash
        return hash(tuple(sorted((n.id, self.apply(n).id) for n in self._domain if self.apply(n) != n)))

    def __repr__(self) -> str:
        cycs = self.cycles()
        if not cycs:
            return "Permutation(identity)"
        cyc_str = "".join("(" + " ".join(str(n) for n in c) + ")" for c in cycs)
        return f"Permutation({cyc_str})"


class APGAutomorphism(Permutation):
    """An automorphism on an AccessiblePointedGraph."""

    def __init__(self, mapping: Mapping[Node, Node]) -> None:
        super().__init__(mapping)

    def inverse(self) -> APGAutomorphism:
        inv_map = {v: k for k, v in self._mapping.items()}
        return APGAutomorphism(inv_map)

    def compose(self, other: Permutation) -> APGAutomorphism:
        dom = set(self._domain) | set(other._domain)
        comp_map = {n: self.apply(other.apply(n)) for n in dom}
        return APGAutomorphism(comp_map)

    def __mul__(self, other: Permutation) -> APGAutomorphism:
        return self.compose(other)


class PermutationGroup:
    """A finite group of permutations closed under composition and inversion."""

    def __init__(self, generators: Iterable[Permutation], domain: Iterable[Node] | None = None) -> None:
        gens = list(generators)
        dom: set[Node] = set()
        if domain is not None:
            dom.update(n if isinstance(n, Node) else Node(n) for n in domain)
        for g in gens:
            dom.update(g.domain)
        self._domain = frozenset(dom)

        # Generate elements via breadth-first group closure
        id_perm = Permutation.identity(self._domain)
        elements: set[Permutation] = {id_perm}
        queue: deque[Permutation] = deque([id_perm])

        while queue:
            curr = queue.popleft()
            for gen in gens:
                nxt = curr * gen
                if nxt not in elements:
                    elements.add(nxt)
                    queue.append(nxt)
                inv_nxt = curr * (~gen)
                if inv_nxt not in elements:
                    elements.add(inv_nxt)
                    queue.append(inv_nxt)

        self._elements = frozenset(elements)
        self.generators = tuple(gens)

    @property
    def domain(self) -> Set[Node]:
        """The underlying set acted upon by this group."""
        return self._domain

    @property
    def order(self) -> int:
        """The number of elements in this group."""
        return len(self._elements)

    def __len__(self) -> int:
        return self.order

    def elements(self) -> list[Permutation]:
        """Return all elements of the group."""
        return list(self._elements)

    def contains(self, perm: Permutation) -> bool:
        """Check if a permutation belongs to this group."""
        return perm in self._elements

    def __contains__(self, perm: Any) -> bool:
        if not isinstance(perm, Permutation):
            return False
        return self.contains(perm)

    def is_abelian(self) -> bool:
        """Return True if all elements of the group commute."""
        elems = list(self._elements)
        for i, a in enumerate(elems):
            for b in elems[i + 1:]:
                if (a * b) != (b * a):
                    return False
        return True

    def orbits(self, nodes: Iterable[Node | Hashable] | None = None) -> list[set[Node]]:
        """The orbits of the group action, over the whole domain or a subset.

        With ``nodes`` given, each orbit is intersected with that subset. If the
        subset is not itself a union of orbits the blocks returned are pieces of
        orbits rather than orbits, and they partition the subset rather than the
        domain -- ask for the whole domain if the orbits themselves are wanted.
        """
        target_nodes = set(self._domain if nodes is None else (n if isinstance(n, Node) else Node(n) for n in nodes))
        visited: set[Node] = set()
        result: list[set[Node]] = []
        elements = list(self._elements)

        for n in sorted(target_nodes, key=lambda x: str(x.id)):
            if n not in visited:
                orb = _orbit_closure(n, elements) & target_nodes
                visited.update(orb)
                result.append(orb)

        return result

    def stabilizer(self, node: Node | Hashable) -> PermutationGroup:
        """Compute the stabilizer subgroup G_x = {g in G : g(x) = x}."""
        n = node if isinstance(node, Node) else Node(node)
        stab_gens = [g for g in self._elements if g.apply(n) == n]
        return PermutationGroup(stab_gens, domain=self._domain)

    def __repr__(self) -> str:
        return f"PermutationGroup(order={self.order}, domain_size={len(self._domain)})"


def trivial_group(domain: Iterable[Node]) -> PermutationGroup:
    """The trivial group {id} acting on domain."""
    dom = list(domain)
    return PermutationGroup([Permutation.identity(dom)], domain=dom)


def cyclic_group(domain: Sequence[Node]) -> PermutationGroup:
    """The cyclic group C_n acting on an ordered sequence of nodes."""
    dom = list(domain)
    if len(dom) <= 1:
        return trivial_group(dom)
    gen = Permutation.from_cycle(dom, dom)
    return PermutationGroup([gen], domain=dom)


def is_apg_automorphism(
    apg: AccessiblePointedGraph,
    perm: Permutation,
    pointed: bool = True,
) -> bool:
    """Check if a permutation is an automorphism of the Accessible Pointed Graph.

    If pointed=True, the root must be a fixed point (perm(root) == root).
    Directed edges must be preserved: (u, v) in E <=> (perm(u), perm(v)) in E.
    """
    if pointed and perm.apply(apg.root) != apg.root:
        return False

    for u in apg.nodes:
        pu = perm.apply(u)
        if pu not in apg.nodes:
            return False
        expected_children = {perm.apply(v) for v in apg.children(u)}
        actual_children = apg.children(pu)
        if expected_children != actual_children:
            return False
    return True





def is_symmetric(apg: AccessiblePointedGraph, aut: Permutation) -> bool:
    """Check if aut is a symmetry of apg."""
    return is_apg_automorphism(apg, aut, pointed=True)


def find_apg_automorphisms(
    apg: AccessiblePointedGraph,
    pointed: bool = True,
) -> PermutationGroup:
    """Compute the automorphism group Aut_r(G) (pointed) or Aut(G) of an APG."""
    aut_list = automorphism_group(apg, pointed=pointed)
    return PermutationGroup(aut_list, domain=apg.nodes)


def automorphism_group(
    apg: AccessiblePointedGraph,
    pointed: bool = True,
) -> list[APGAutomorphism]:
    """Compute all automorphisms of the given APG."""
    nodes = sorted(apg.nodes, key=lambda x: str(x.id))
    n = len(nodes)
    if n == 0:
        return []
    if n == 1:
        return [APGAutomorphism({nodes[0]: nodes[0]})]

    root = apg.root
    node_to_idx = {node: i for i, node in enumerate(nodes)}
    out_degrees = [len(apg.children(node)) for node in nodes]

    valid_automorphisms: list[APGAutomorphism] = []
    fixed_indices = {node_to_idx[root]: node_to_idx[root]} if pointed else {}

    assignment: list[int] = [-1] * n
    used: list[bool] = [False] * n

    for k, v in fixed_indices.items():
        assignment[k] = v
        used[v] = True

    def backtrack(curr_idx: int) -> None:
        if curr_idx == n:
            m = {nodes[i]: nodes[assignment[i]] for i in range(n)}
            p = APGAutomorphism(m)
            if is_apg_automorphism(apg, p, pointed=pointed):
                valid_automorphisms.append(p)
            return

        if assignment[curr_idx] != -1:
            backtrack(curr_idx + 1)
            return

        u_deg = out_degrees[curr_idx]

        for cand_idx in range(n):
            if not used[cand_idx] and out_degrees[cand_idx] == u_deg:
                assignment[curr_idx] = cand_idx
                used[cand_idx] = True
                backtrack(curr_idx + 1)
                assignment[curr_idx] = -1
                used[cand_idx] = False

    backtrack(0)
    return valid_automorphisms


def _orbit_closure(node: Node, permutations: Sequence[Permutation]) -> set[Node]:
    """Every node reachable from ``node`` by repeated application of ``permutations``.

    This is the orbit under the group the permutations generate, whether they are
    a generating set or the whole group: a group already contains every composite,
    so closing over it adds nothing, while closing over a generating set is the
    difference between the orbit and the one-step image set.

    Terminates because each permutation has finite order and the reachable set is
    bounded by the union of their domains.
    """
    seen: set[Node] = {node}
    queue: list[Node] = [node]
    while queue:
        point = queue.pop()
        for perm in permutations:
            image = perm.apply(point)
            if image not in seen:
                seen.add(image)
                queue.append(image)
    return seen


def orbit(node: Node | Hashable, group: Iterable[Permutation]) -> set[Node]:
    """The orbit of ``node`` under the group generated by ``group``.

    ``group`` may be a full group or a generating set; both give the orbit. It
    previously applied each supplied permutation once, which is the orbit only in
    the first case. Under the cyclic group generated by ``(0 1 2 3 4)`` the orbit
    of node 0 is all five nodes, and passing ``PermutationGroup.generators`` --
    a public attribute -- returned ``{1}``.
    """
    n = node if isinstance(node, Node) else Node(node)
    return _orbit_closure(n, list(group))


def all_orbits(apg: AccessiblePointedGraph, group: Iterable[Permutation]) -> list[set[Node]]:
    """The orbits of ``apg``'s nodes under ``group``, as a partition.

    Distinct orbits are disjoint and together cover every node, which is what
    makes the quotient by them well defined. That was not true when a generating
    set was supplied: the one-step image sets left nodes in no block at all, and
    ``quotient_by_symmetry`` then failed on a missing key.

    Orbits are intersected with the graph's own nodes, so a permutation whose
    domain reaches outside the graph does not widen a block.
    """
    target_nodes = set(apg.nodes)
    visited: set[Node] = set()
    result: list[set[Node]] = []
    permutations = list(group)

    for n in sorted(target_nodes, key=lambda x: str(x.id)):
        if n not in visited:
            orb = _orbit_closure(n, permutations) & target_nodes
            visited.update(orb)
            result.append(orb)

    return result


def quotient_by_symmetry(
    apg: AccessiblePointedGraph,
    group: Iterable[Permutation] | PermutationGroup,
) -> AccessiblePointedGraph:
    """Quotient an APG by symmetry orbits."""
    g_iter = group.elements() if isinstance(group, PermutationGroup) else group
    orbs = all_orbits(apg, g_iter)

    # Node to orbit id
    node_to_block: dict[Node, int] = {}
    for block_id, orb in enumerate(orbs):
        for n in orb:
            node_to_block[n] = block_id

    unblocked = [u for u in apg.nodes if u not in node_to_block]
    if unblocked:
        # Unreachable while all_orbits returns a partition. Kept so that a
        # regression there surfaces here as a diagnosis rather than as a KeyError
        # from an internal dict, which is what it used to be.
        raise ValueError(
            f"{len(unblocked)} node(s) fall in no orbit, so the quotient is not "
            f"defined: {sorted(str(u.id) for u in unblocked)[:5]}. The supplied "
            f"permutations do not partition the graph's nodes"
        )

    root_block = node_to_block[apg.root]
    block_nodes: dict[int, Node] = {root_block: Node(0, label=f"orb_{root_block}")}
    queue: deque[int] = deque([root_block])
    next_id = 1

    raw_block_edges: dict[int, set[int]] = {}
    for u in apg.nodes:
        b_u = node_to_block[u]
        raw_block_edges.setdefault(b_u, set())
        for v in apg.children(u):
            b_v = node_to_block[v]
            raw_block_edges[b_u].add(b_v)

    while queue:
        curr_b = queue.popleft()
        for child_b in sorted(raw_block_edges.get(curr_b, set())):
            if child_b not in block_nodes:
                block_nodes[child_b] = Node(next_id, label=f"orb_{child_b}")
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


def symmetry_group_order(target: AccessiblePointedGraph | Hyperset) -> int:
    """Return the order of the automorphism group of an APG or Hyperset."""
    apg = target.apg if isinstance(target, Hyperset) else target
    return len(automorphism_group(apg, pointed=True))


def find_hyperset_automorphisms(hyperset: Hyperset, pointed: bool = True) -> PermutationGroup:
    """Compute the automorphism group of the underlying APG of a hyperset."""
    return find_apg_automorphisms(hyperset.apg, pointed=pointed)


def orbit_quotient_apg(
    apg: AccessiblePointedGraph,
    group: PermutationGroup,
) -> AccessiblePointedGraph:
    """Quotient an APG by group orbits."""
    return quotient_by_symmetry(apg, group)


def orbit_quotient_hyperset(
    hyperset: Hyperset,
    group: PermutationGroup,
) -> Hyperset:
    """Construct the orbit-quotient hyperset under a group of symmetries."""
    return Hyperset(orbit_quotient_apg(hyperset.apg, group))


def is_invariant_under(hyperset: Hyperset, group: PermutationGroup) -> bool:
    """Check if a hyperset is invariant under every transformation in the group."""
    for g in group.elements():
        transformed_edges: dict[Node, set[Node]] = {}
        for u in hyperset.apg.nodes:
            pu = g.apply(u)
            transformed_edges[pu] = {g.apply(v) for v in hyperset.apg.children(u)}
        transformed_root = g.apply(hyperset.apg.root)
        transformed_apg = AccessiblePointedGraph(root=transformed_root, edges=transformed_edges)
        if not bisimilar(hyperset.apg, transformed_apg):
            return False
    return True


def discrete_derivative(hyperset: Hyperset, transformation: Permutation) -> Hyperset:
    """Discrete transformation derivative: Delta_g(H) = (g(H) \\ H) U (H \\ g(H))."""
    transformed_edges: dict[Node, set[Node]] = {}
    for u in hyperset.apg.nodes:
        pu = transformation.apply(u)
        transformed_edges[pu] = {transformation.apply(v) for v in hyperset.apg.children(u)}
    transformed_root = transformation.apply(hyperset.apg.root)
    transformed_h = Hyperset(AccessiblePointedGraph(root=transformed_root, edges=transformed_edges))

    diff1 = hyperset - transformed_h
    diff2 = transformed_h - hyperset
    return diff1 | diff2
