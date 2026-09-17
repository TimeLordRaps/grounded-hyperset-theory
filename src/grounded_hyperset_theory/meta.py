"""Meta-features for Grounded Hyperset Theory: Abstraction, Objectification, and Meta-Fractalization."""

from __future__ import annotations

from typing import Callable, Hashable, Iterable, Mapping

from .graph import AccessiblePointedGraph, Node
from .hyperset import EmptyHyperset, Hyperset, QuineAtom, pair, von_neumann_ordinal


class Abstraction:
    """A formal abstraction lambda x. M over a Hyperset or APG body."""

    def __init__(self, variable: Node | Hashable, body: Hyperset) -> None:
        self.variable = variable if isinstance(variable, Node) else Node(variable)
        self.body = body

    def instantiate(self, argument: Hyperset) -> Hyperset:
        """Instantiate this abstraction by substituting occurrences of variable with argument.

        Constructs the substituted APG and returns its canonical bisimulation quotient.
        """
        body_apg = self.body.apg
        var_node = self.variable
        arg_apg = argument.apg

        # Check if variable occurs in the body APG
        var_occurrences = {n for n in body_apg.nodes if n == var_node or n.id == var_node.id}
        if not var_occurrences:
            return self.body

        # Build combined node and edge dictionaries with namespacing
        new_edges: dict[Node, set[Node]] = {}

        # 1. Map argument nodes to a distinct namespace
        arg_root = arg_apg.root
        mapped_arg_root = Node(("arg_root", arg_root.id), label=arg_root.label)

        arg_node_map: dict[Node, Node] = {arg_root: mapped_arg_root}
        for n in arg_apg.nodes:
            if n != arg_root:
                arg_node_map[n] = Node(("arg", n.id), label=n.label)

        for n, children in arg_apg._edges.items():
            mapped_p = arg_node_map[n]
            new_edges[mapped_p] = {arg_node_map[c] for c in children}

        # 2. Add body nodes (excluding the variable nodes themselves)
        for n in body_apg.nodes:
            if n in var_occurrences:
                continue
            mapped_children: set[Node] = set()
            for c in body_apg.children(n):
                if c in var_occurrences:
                    mapped_children.add(mapped_arg_root)
                else:
                    mapped_children.add(c)
            new_edges[n] = mapped_children

        # 3. Determine new root
        if body_apg.root in var_occurrences:
            new_root = mapped_arg_root
        else:
            new_root = body_apg.root

        new_apg = AccessiblePointedGraph(root=new_root, edges=new_edges)
        return Hyperset(new_apg).canonical()

    def __call__(self, argument: Hyperset) -> Hyperset:
        return self.instantiate(argument)

    def to_hyperset(self) -> Hyperset:
        """Objectify this abstraction into a first-class Hyperset tag pair."""
        # Tag 1 represents an abstraction: (1, (var, body))
        var_node = Node(f"var:{self.variable.id}", label=str(self.variable))
        var_hyperset = Hyperset(AccessiblePointedGraph(root=var_node, edges={var_node: ()}))
        tag = Hyperset.from_elements(EmptyHyperset())
        return pair(tag, pair(var_hyperset, self.body))

    def __repr__(self) -> str:
        return f"Abstraction(λ{self.variable}. {self.body})"


def abstract(
    target: Hyperset,
    parameter: Node | Hashable,
    var_name: str | Hashable = "x",
) -> Abstraction:
    """Abstract a sub-hyperset or node within target into a formal parameter variable."""
    p_node = parameter if isinstance(parameter, Node) else Node(parameter)
    var_node = Node(var_name, label=str(var_name))

    # Replace parameter nodes in target with var_node
    target_apg = target.apg
    new_edges: dict[Node, set[Node]] = {}
    matches = {n for n in target_apg.nodes if n == p_node or n.id == p_node.id}

    for n in target_apg.nodes:
        mapped_n = var_node if n in matches else n
        if mapped_n not in new_edges:
            new_edges[mapped_n] = set()
        for c in target_apg.children(n):
            mapped_c = var_node if c in matches else c
            new_edges[mapped_n].add(mapped_c)

    new_root = var_node if target_apg.root in matches else target_apg.root
    abstracted_body = Hyperset(AccessiblePointedGraph(root=new_root, edges=new_edges))
    return Abstraction(variable=var_node, body=abstracted_body)


def objectify_relation(pairs: Iterable[tuple[Hyperset, Hyperset]]) -> Hyperset:
    """Objectify an iterable of Hyperset pairs (a, b) into a first-class Hyperset relation."""
    pair_hypersets = [pair(a, b) for a, b in pairs]
    if not pair_hypersets:
        return EmptyHyperset()
    return Hyperset.from_elements(*pair_hypersets)


def _unpack_pair(pair_hyperset: Hyperset) -> tuple[Hyperset, Hyperset]:
    """Unpack a Kuratowski ordered pair (a, b) = {{a}, {a, b}}."""
    members = pair_hyperset.members()
    distinct: list[Hyperset] = []
    for m in members:
        if not any(m == d for d in distinct):
            distinct.append(m)

    if len(distinct) == 1:
        # Case (a, a) = {{a}, {a, a}} = {{a}}
        singleton_members = distinct[0].members()
        d_sing: list[Hyperset] = []
        for sm in singleton_members:
            if not any(sm == d for d in d_sing):
                d_sing.append(sm)
        if len(d_sing) != 1:
            raise ValueError("Malformed Kuratowski pair: singleton expected")
        a = d_sing[0]
        return (a, a)
    elif len(distinct) == 2:
        # One is {a}, other is {a, b}
        m0_elems: list[Hyperset] = []
        for e in distinct[0].members():
            if not any(e == d for d in m0_elems):
                m0_elems.append(e)
        m1_elems: list[Hyperset] = []
        for e in distinct[1].members():
            if not any(e == d for d in m1_elems):
                m1_elems.append(e)

        if len(m0_elems) == 1 and len(m1_elems) == 2:
            a = m0_elems[0]
            b_cand = [x for x in m1_elems if x != a]
            if not b_cand:
                raise ValueError("Malformed Kuratowski pair components")
            return (a, b_cand[0])
        elif len(m1_elems) == 1 and len(m0_elems) == 2:
            a = m1_elems[0]
            b_cand = [x for x in m0_elems if x != a]
            if not b_cand:
                raise ValueError("Malformed Kuratowski pair components")
            return (a, b_cand[0])
        else:
            raise ValueError(f"Malformed Kuratowski pair with sizes ({len(m0_elems)}, {len(m1_elems)})")
    else:
        raise ValueError(f"Malformed Kuratowski pair: expected 1 or 2 distinct members, got {len(distinct)}")


def deobjectify_relation(hyperset: Hyperset) -> list[tuple[Hyperset, Hyperset]]:
    """Decode a relation hyperset into a list of constituent (domain, codomain) pairs."""
    result: list[tuple[Hyperset, Hyperset]] = []
    for m in hyperset.members():
        p = _unpack_pair(m)
        result.append(p)
    return result


def objectify_function(mapping: Mapping[Hyperset, Hyperset]) -> Hyperset:
    """Reify a function mapping into a first-class Hyperset object."""
    return objectify_relation(mapping.items())


def deobjectify_function(hyperset: Hyperset) -> dict[Hyperset, Hyperset]:
    """Decode a hyperset function, verifying single-valued functionality."""
    pairs = deobjectify_relation(hyperset)
    func: dict[Hyperset, Hyperset] = {}
    for dom, codom in pairs:
        if dom in func:
            if func[dom] != codom:
                raise ValueError("Not a well-defined function: domain element maps to multiple values")
        else:
            func[dom] = codom
    return func


def objectify_apg(apg: AccessiblePointedGraph) -> Hyperset:
    """Encode an entire AccessiblePointedGraph (V, E, r) as a first-class Hyperset."""
    nodes_list = sorted(list(apg.nodes), key=lambda n: str(n.id))
    node_to_idx = {n: i for i, n in enumerate(nodes_list)}
    root_idx = node_to_idx[apg.root]

    edge_pairs: list[tuple[Hyperset, Hyperset]] = []
    for parent, children in apg._edges.items():
        p_idx = node_to_idx[parent]
        for child in children:
            c_idx = node_to_idx[child]
            edge_pairs.append((von_neumann_ordinal(p_idx), von_neumann_ordinal(c_idx)))

    edges_h = objectify_relation(edge_pairs)
    root_h = von_neumann_ordinal(root_idx)
    return pair(root_h, edges_h)


def deobjectify_apg(hyperset: Hyperset) -> AccessiblePointedGraph:
    """Decode an objectified APG hyperset back into an AccessiblePointedGraph."""
    root_h, edges_h = _unpack_pair(hyperset)
    root_idx = root_h.to_int()
    raw_pairs = deobjectify_relation(edges_h)

    edges_dict: dict[Node, set[Node]] = {}
    all_nodes: set[int] = {root_idx}
    for p_h, c_h in raw_pairs:
        u = p_h.to_int()
        v = c_h.to_int()
        all_nodes.add(u)
        all_nodes.add(v)
        edges_dict.setdefault(Node(u), set()).add(Node(v))

    for n in all_nodes:
        if Node(n) not in edges_dict:
            edges_dict[Node(n)] = set()

    return AccessiblePointedGraph(root=Node(root_idx), edges=edges_dict)


def fractal_hyperset(pattern: str = "quine_nested") -> Hyperset:
    """Generate archetypal non-well-founded fractal hypersets under Aczel's AFA."""
    if pattern == "quine":
        return QuineAtom()
    elif pattern == "quine_nested":
        # Phi = {Phi, {Phi, ∅}}
        # Solves equations: Phi -> [Phi, S], S -> [Phi, empty], empty -> []
        phi = Node("Φ", label="Φ")
        s = Node("S", label="{Φ, ∅}")
        empty = Node("∅", label="∅")
        apg = AccessiblePointedGraph(root=phi, edges={phi: [phi, s], s: [phi, empty], empty: []})
        return Hyperset(apg)
    elif pattern == "sierpinski":
        # 3-cycle self-referential graph: A -> [B, C], B -> [A, C], C -> [A, B]
        a, b, c = Node("A"), Node("B"), Node("C")
        apg = AccessiblePointedGraph(root=a, edges={a: [b, c], b: [a, c], c: [a, b]})
        return Hyperset(apg)
    elif pattern == "cantor_non_well_founded":
        # Binary branching self-similar: K -> [KL, KR], KL -> [K, ∅], KR -> [∅, K]
        k, kl, kr, empty = Node("K"), Node("KL"), Node("KR"), Node("∅")
        edges = {
            k: [kl, kr],
            kl: [k, empty],
            kr: [empty, k],
            empty: [],
        }
        return Hyperset(AccessiblePointedGraph(root=k, edges=edges))
    else:
        raise ValueError(f"Unknown fractal hyperset pattern: {pattern}")


def meta_fractalize(
    seed: Hyperset,
    rule: Callable[[Hyperset], Iterable[Hyperset]] | Mapping[Hyperset, Iterable[Hyperset]],
    depth: int = 2,
) -> Hyperset:
    """Recursively expand a hyperset into a self-similar fractal hyperset up to depth."""
    if depth <= 0:
        return seed

    current = seed
    for _ in range(depth):
        new_members: list[Hyperset] = []
        for m in current.members():
            if callable(rule):
                expanded = list(rule(m))
            elif isinstance(rule, Mapping):
                expanded = list(rule.get(m, [m]))
            else:
                expanded = [m]
            new_members.extend(expanded)
        current = Hyperset.from_elements(*new_members)
    return current


def unfold_step(hyperset: Hyperset) -> Hyperset:
    """Unfold one level of membership without altering the AFA bisimulation class."""
    # Each child c of root is replaced with a fresh copy of c's children
    root = hyperset.apg.root
    new_root = Node(f"unfolded_{root.id}")
    new_edges: dict[Node, set[Node]] = {new_root: set()}

    for c in hyperset.apg.children(root):
        c_copy = Node(f"copy_{c.id}")
        new_edges[new_root].add(c_copy)
        for n in hyperset.apg.nodes:
            mapped_n = c_copy if n == c else Node(f"copy_{c.id}_{n.id}")
            if mapped_n not in new_edges:
                new_edges[mapped_n] = set()
            for child in hyperset.apg.children(n):
                mapped_child = c_copy if child == c else Node(f"copy_{c.id}_{child.id}")
                new_edges[mapped_n].add(mapped_child)

    unfolded_apg = AccessiblePointedGraph(root=new_root, edges=new_edges)
    return Hyperset(unfolded_apg)
