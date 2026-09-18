"""Symbolic dynamics of symbolic representational calculi, rewriting systems, and bisimulation on trajectories."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, Set

from .graph import AccessiblePointedGraph, Node
from .hyperset import Hyperset, bisimilar


@dataclass(frozen=True)
class RewriteRule:
    """A rewrite or state transition rule operating on Hypersets or symbolic states."""

    name: str
    transform: Callable[[Hyperset], Iterable[Hyperset]]

    def apply(self, state: Hyperset) -> list[Hyperset]:
        """Apply this rule to state, returning all valid next states.

        An empty list means the rule does not apply here. It does **not** mean
        the rule failed: a raising transform used to be caught and reported as
        an empty list, which made a crashing rule indistinguishable from an
        inapplicable one. A `ZeroDivisionError` in a rule body then produced
        ``matches() is False``, ``step() == []`` and a one-state reduction graph
        whose only state was reported as a normal form -- a confident answer
        from a rule that had never once run to completion.

        Raises:
            RuntimeError: if the transform raises, naming the rule and the state.
                Write the applicability condition into the transform as a guard
                returning ``[]``; do not express it by raising.
        """
        try:
            return list(self.transform(state))
        except Exception as exc:  # noqa: BLE001 - re-raised with context below
            raise RuntimeError(
                f"rewrite rule {self.name!r} raised on state {state!r}: "
                f"{type(exc).__name__}: {exc}. A rule that does not apply must "
                f"return an empty list; raising is not a way to say that."
            ) from exc

    def matches(self, state: Hyperset) -> bool:
        return len(self.apply(state)) > 0


class RewritingSystem:
    """A symbolic rewriting system defining discrete state transition dynamics."""

    def __init__(self, rules: Sequence[RewriteRule], name: str = "calculus") -> None:
        self.rules = tuple(rules)
        self.name = name

    def step(self, state: Hyperset) -> list[Hyperset]:
        """Compute all one-step transitions from state across all rules."""
        distinct_next: list[Hyperset] = []
        for r in self.rules:
            for nxt in r.apply(state):
                if not any(nxt == d for d in distinct_next):
                    distinct_next.append(nxt)
        return distinct_next

    def step_deterministic(self, state: Hyperset) -> Hyperset | None:
        """The first result of the first applicable rule, or None in normal form.

        This resolves nondeterminism by rule order, so it follows one strategy
        through the system rather than describing the system. Two systems with
        the same rules in a different order take different paths here and the
        same reduction graph in ``reduction_apg``. ``None`` means no rule
        applies, which with the fix to ``RewriteRule.apply`` now really does mean
        that rather than also covering a rule that raised.
        """
        for r in self.rules:
            nxt = r.apply(state)
            if nxt:
                return nxt[0]
        return None

    def trace(self, initial_state: Hyperset, max_steps: int = 100) -> list[Hyperset]:
        """A deterministic execution trace from `initial_state` under rule order.

        The trace stops for one of three reasons and the returned list does not
        say which: a normal form was reached, a state repeated, or `max_steps`
        ran out. Those are different facts and only the first is a result about
        the system. To tell them apart::

            path = system.trace(start, max_steps=n)
            reached_normal_form = system.step_deterministic(path[-1]) is None
            repeated = path[-1] in path[:-1]
            ran_out = len(path) > n and not reached_normal_form

        A diverging system with `max_steps=3` and a system that halts after
        three steps both return a plain list of states; nothing in the list
        distinguishes them.
        """
        history = [initial_state]
        curr = initial_state
        for _ in range(max_steps):
            nxt = self.step_deterministic(curr)
            if nxt is None or any(nxt == h for h in history):
                if nxt is not None:
                    history.append(nxt)
                break
            history.append(nxt)
            curr = nxt
        return history

    def reduction_apg(
        self,
        initial_state: Hyperset,
        max_depth: int = 10,
        max_states: int = 100,
    ) -> AccessiblePointedGraph:
        """The complete transition state APG rooted at `initial_state`.

        Nodes correspond to states up to bisimulation -- `Hyperset.__eq__` is
        bisimulation, so two states built differently that denote the same set
        are one node. Edges are the one-step rewrites.

        The graph is **complete**: every reachable state is present and every
        transition out of every state is an edge. That is what makes the rest of
        this module mean anything, because here a node with no children is read
        as a normal form, and a truncated search produces nodes with no children
        for an entirely different reason -- they were simply never expanded.
        Both budgets used to truncate silently, and four functions read the
        horizon as a result: `normal_forms` returned it, `find_attractors`
        reported an attractor for a system that has none, `is_terminating`
        called a diverging system terminating, and `is_confluent` answered about
        the budget rather than the system.

        Raises:
            ValueError: if the reachable state space does not fit in
                `max_states`, or if it is deeper than `max_depth`. Raise the
                budget; there is no caller in this module for which a fragment
                is the right answer.
        """
        if max_states < 1:
            raise ValueError(f"max_states must be at least 1, got {max_states}")
        if max_depth < 0:
            raise ValueError(f"max_depth must be non-negative, got {max_depth}")

        states: list[Hyperset] = [initial_state]
        state_to_node: dict[int, Node] = {0: Node(0, label="s0")}
        edges: dict[Node, set[Node]] = {state_to_node[0]: set()}

        queue: deque[tuple[int, int]] = deque([(0, 0)])

        while queue:
            curr_idx, depth = queue.popleft()
            curr_state = states[curr_idx]
            curr_node = state_to_node[curr_idx]
            successors = self.step(curr_state)

            if depth >= max_depth:
                if successors:
                    raise ValueError(
                        f"the reachable state space of {self.name!r} from the "
                        f"given start is deeper than max_depth={max_depth}: "
                        f"state s{curr_idx} sits at the horizon and still has "
                        f"{len(successors)} transition(s). Raise max_depth; a "
                        f"truncated graph reports its horizon as normal forms."
                    )
                continue

            for next_state in successors:
                existing_idx = None
                for idx, s in enumerate(states):
                    if s == next_state:
                        existing_idx = idx
                        break

                if existing_idx is None:
                    if len(states) >= max_states:
                        raise ValueError(
                            f"the reachable state space of {self.name!r} from "
                            f"the given start does not fit in max_states="
                            f"{max_states}. Raise the budget; dropping the "
                            f"transition would leave s{curr_idx} looking like a "
                            f"normal form."
                        )
                    new_idx = len(states)
                    states.append(next_state)
                    new_node = Node(new_idx, label=f"s{new_idx}")
                    state_to_node[new_idx] = new_node
                    edges[new_node] = set()
                    edges[curr_node].add(new_node)
                    queue.append((new_idx, depth + 1))
                else:
                    edges[curr_node].add(state_to_node[existing_idx])

        return AccessiblePointedGraph(root=state_to_node[0], edges=edges)

    def find_attractors(
        self,
        start: Hyperset,
        max_depth: int = 20,
    ) -> list[Hyperset]:
        """The normal forms reachable from `start`: states with no transition out.

        Terminal states only. The docstring used to promise "or cyclic
        attractors" and no cyclic attractor was ever returned -- the body
        collects nodes with no children, and a cycle has none such. For the
        cyclic case use `terminal_sccs`, which returns the terminal strongly
        connected components of the same graph; together the two are the
        attractors of the dynamics.

        With `reduction_apg` no longer truncating, a node with no children is
        now genuinely a normal form. It previously included the depth horizon,
        so this reported one attractor for `n -> n+1`, which has none.

        Raises:
            ValueError: if the reachable state space exceeds the budget.
        """
        apg = self.reduction_apg(start, max_depth=max_depth)
        terminals = [n for n in apg.nodes if len(apg.children(n)) == 0]
        attractor_hypersets: list[Hyperset] = []
        for t in terminals:
            attractor_hypersets.append(Hyperset(apg.subgraph_from(t)))
        return attractor_hypersets

    def is_confluent(
        self,
        start: Hyperset,
        max_depth: int = 6,
        max_states: int = 50,
    ) -> bool:
        """Whether the system is confluent on the states reachable from `start`.

        Confluent means any two states reachable from a common ancestor have a
        common descendant -- the Church-Rosser property, not the weaker local
        confluence and not the stronger diamond property. The old docstring
        named all three; the old body computed the weakest, over a graph that
        had been silently truncated, so neither answer was about the system.
        Huet's counterexample separates the two properties: `a <-> b`, `a -> c`,
        `b -> d` with `c` and `d` distinct normal forms is locally confluent and
        is not confluent, and Newman's lemma does not lift it because `a <-> b`
        does not terminate.

        Decided rather than searched. On a finite complete reduction graph:

            the graph is confluent from its root
              iff its SCC condensation has exactly one terminal SCC.

        Two terminal SCCs and nothing in one joins anything in the other, so
        confluence fails. Exactly one and every state reaches it, since walking
        forward in the condensation DAG must end at a sink and there is only one
        -- and being strongly connected it joins any two states inside itself.
        The set reachable from any state is closed under successors, so the root
        decides it for every state, and `terminal_sccs` computes them. An answer
        about the system rather than about the budget.

        Raises:
            ValueError: if the reachable state space exceeds the budget. A
                partial graph cannot decide this: a join one step past the
                horizon reads as a failure to join, and a divergence past the
                horizon reads as an absence of divergence.
        """
        apg = self.reduction_apg(start, max_depth=max_depth, max_states=max_states)
        return len(terminal_sccs(apg)) == 1

    @staticmethod
    def _descendants(apg: AccessiblePointedGraph, start: Node) -> set[Node]:
        """Every node reachable from `start`, including `start` itself."""
        visited: set[Node] = {start}
        queue: deque[Node] = deque([start])
        while queue:
            curr = queue.popleft()
            for child in apg.children(curr):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return visited


RewriteSystem = RewritingSystem


@dataclass(frozen=True)
class RewriteTrajectory:
    """A trajectory of sequential state transitions in a representational calculus."""

    states: tuple[Hyperset, ...]

    def to_apg(self) -> AccessiblePointedGraph:
        """Convert the trajectory into a directed path/cycle AccessiblePointedGraph."""
        if not self.states:
            root = Node(0, label="empty_traj")
            return AccessiblePointedGraph(root=root, edges={root: ()})

        state_nodes: list[Node] = []
        for i, s in enumerate(self.states):
            matched_idx = None
            for j in range(i):
                if s == self.states[j]:
                    matched_idx = j
                    break
            if matched_idx is not None:
                state_nodes.append(state_nodes[matched_idx])
            else:
                state_nodes.append(Node(i, label=f"t{i}"))

        edges: dict[Node, set[Node]] = {n: set() for n in state_nodes}
        for i in range(len(state_nodes) - 1):
            edges[state_nodes[i]].add(state_nodes[i + 1])

        return AccessiblePointedGraph(root=state_nodes[0], edges=edges)


def trajectory_bisimilar(
    traj1: RewriteTrajectory | RewritingSystem,
    traj2: RewriteTrajectory | RewritingSystem,
    init1: Hyperset | None = None,
    init2: Hyperset | None = None,
    max_states: int = 100,
    max_depth: int = 10,
) -> bool:
    """Whether two trajectories, or two systems from given starts, are bisimilar.

    Bisimulation is under Aczel's AFA, so this is equality of the hypersets the
    two graphs denote.

    `max_depth` is now a parameter. It was always being applied -- through
    `reduction_apg`'s own default of 10 -- while only `max_states` was exposed,
    so raising `max_states` to 100 on a 31-state system still compared 11-state
    graphs and the parameter that looked like the control was not the binding
    one. Both budgets now raise rather than truncate, so an insufficient budget
    is an error instead of a quietly different question.

    Raises:
        ValueError: if either reachable state space exceeds the budgets.
        TypeError: if the two arguments are not both trajectories or both
            systems.
    """
    if isinstance(traj1, RewriteTrajectory) and isinstance(traj2, RewriteTrajectory):
        return bisimilar(traj1.to_apg(), traj2.to_apg())

    if isinstance(traj1, RewritingSystem) and isinstance(traj2, RewritingSystem):
        if init1 is None or init2 is None:
            raise ValueError("init1 and init2 required when comparing RewritingSystems")
        g1 = traj1.reduction_apg(init1, max_depth=max_depth, max_states=max_states)
        g2 = traj2.reduction_apg(init2, max_depth=max_depth, max_states=max_states)
        return bisimilar(g1, g2)

    raise TypeError("Arguments must be both RewriteTrajectory or both RewritingSystem")


def trajectory_quotient(traj: RewriteTrajectory) -> AccessiblePointedGraph:
    """Compute the canonical strongly extensional bisimulation quotient of a rewrite trajectory."""
    return traj.to_apg().bisimulation_quotient()


def build_trajectory_apg(
    initial_state: Hyperset,
    system: RewritingSystem,
    max_states: int = 100,
    max_depth: int = 10,
) -> AccessiblePointedGraph:
    """Generate the state-transition trajectory APG of a calculus from an initial state."""
    return system.reduction_apg(initial_state, max_depth=max_depth, max_states=max_states)


def trajectory_hyperset(
    initial_state: Hyperset,
    system: RewritingSystem,
    max_states: int = 100,
    max_depth: int = 10,
) -> Hyperset:
    """Ground the execution trajectory of a calculus into a first-class Hyperset."""
    return Hyperset(build_trajectory_apg(initial_state, system, max_states=max_states, max_depth=max_depth))


def normal_forms(trajectory: AccessiblePointedGraph) -> Set[Node]:
    """The states of `trajectory` with no transition out.

    These are normal forms **if `trajectory` is complete** -- if every reachable
    state is present with all of its transitions. A node with no children in a
    truncated graph is a node that was never expanded, and it is byte-for-byte
    indistinguishable from a real normal form. Graphs from `reduction_apg` are
    complete now, because it refuses to truncate; a graph assembled by hand is
    the caller's responsibility.
    """
    return frozenset(n for n in trajectory.nodes if len(trajectory.children(n)) == 0)


def is_terminating(trajectory: AccessiblePointedGraph) -> bool:
    """Whether `trajectory` is acyclic.

    For a **complete** reduction graph that is termination: finitely many states,
    no cycle, so every path reaches a normal form. For a truncated one it means
    nothing, and the old docstring's claim that acyclicity "proves guaranteed
    termination" was false for exactly that reason -- `n -> n+1` from 0 never
    halts, never repeats a state, and its depth-5 fragment is a 6-state acyclic
    chain, so this returned True for a system that does not terminate.

    `reduction_apg` now refuses to truncate, which is what makes the statement
    transfer from the graph to the system.
    """
    return not trajectory.has_cycles()


def _reachable_from(trajectory: AccessiblePointedGraph, start: Node) -> set[Node]:
    """Every node reachable from `start`, including `start` itself."""
    seen: set[Node] = {start}
    queue: deque[Node] = deque([start])
    while queue:
        curr = queue.popleft()
        for child in trajectory.children(curr):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return seen


def find_periodic_orbits(
    trajectory: AccessiblePointedGraph, max_cycles: int = 1000
) -> list[list[Node]]:
    """Every simple cycle in `trajectory`, each listed once, starting at its
    lowest-ordered node.

    The previous implementation did not find all of them. It ran one DFS from
    the root with a `visited` set that was never cleared, so a node reached a
    second time was skipped and any cycle whose nodes are never all on the stack
    together was invisible. On `1->2, 1->3, 2->3, 3->1, 3->2` it returned two of
    the three simple cycles: `(1,2,3)` and `(2,3)` were found, `(1,3)` was not.

    Enumeration is rooted: each simple cycle is searched for only from its
    lowest-ordered node, over the subgraph of nodes at or above that one in the
    order. That yields every simple cycle exactly once with no deduplication
    pass, since a cycle has exactly one lowest-ordered node.

    Args:
        trajectory: the graph to enumerate. Ordering is by `str(node.id)`, so
            the output is deterministic.
        max_cycles: refuse past this many. The number of simple cycles is
            exponential in the size of the graph in general, which is a reason
            to bound the work and not a reason to return an arbitrary subset of
            the answer.

    Raises:
        ValueError: if `trajectory` has more than `max_cycles` simple cycles.
    """
    if max_cycles < 0:
        raise ValueError(f"max_cycles must be non-negative, got {max_cycles}")

    order = sorted(trajectory.nodes, key=lambda n: str(n.id))
    rank = {node: i for i, node in enumerate(order)}
    cycles: list[list[Node]] = []

    for lowest_rank, lowest in enumerate(order):
        path: list[Node] = [lowest]
        on_path: set[Node] = {lowest}

        def extend(curr: Node, lowest: Node = lowest, floor: int = lowest_rank) -> None:
            for nxt in sorted(trajectory.children(curr), key=lambda n: str(n.id)):
                if rank[nxt] < floor:
                    continue
                if nxt == lowest:
                    if len(cycles) >= max_cycles:
                        raise ValueError(
                            f"the graph has more than max_cycles={max_cycles} "
                            f"simple cycles; raise the budget rather than "
                            f"accepting an arbitrary subset of them"
                        )
                    cycles.append(list(path))
                elif nxt not in on_path:
                    path.append(nxt)
                    on_path.add(nxt)
                    extend(nxt)
                    path.pop()
                    on_path.remove(nxt)

        extend(lowest)

    return cycles


def terminal_sccs(trajectory: AccessiblePointedGraph) -> list[frozenset[Node]]:
    """The terminal strongly connected components of `trajectory`.

    A terminal SCC is one with no transition leaving it: once inside, the
    dynamics stay inside. These are the attractors of the system -- a singleton
    terminal SCC with no self-loop is a normal form, and a larger one is a
    cyclic attractor, the case `find_attractors` described and never returned.

    Exactly one terminal SCC is also the decision procedure for confluence; see
    `RewritingSystem.is_confluent`.

    Meaningful only for a complete graph, for the reason given in
    `normal_forms`.
    """
    reach = {n: _reachable_from(trajectory, n) for n in trajectory.nodes}
    sinks: list[frozenset[Node]] = []
    accounted: set[Node] = set()
    for node in sorted(trajectory.nodes, key=lambda n: str(n.id)):
        if node in accounted:
            continue
        component = reach[node]
        # `component` is closed under transitions by construction. If every state
        # in it also reaches `node`, the states are mutually reachable and none
        # of them leaves, which is exactly a terminal SCC. If some state does not
        # reach back, `node` sits upstream of a sink rather than inside one.
        if all(node in reach[other] for other in component):
            sinks.append(frozenset(component))
            accounted |= component
    return sinks


def is_locally_confluent(trajectory: AccessiblePointedGraph) -> bool:
    """Whether every one-step fork in `trajectory` rejoins somewhere.

    This is local confluence, also called weak Church-Rosser, and it is a
    strictly weaker property than confluence. Newman's lemma lifts it to
    confluence only for **terminating** systems. Huet's counterexample shows the
    gap: `a <-> b`, `a -> c`, `b -> d` with `c` and `d` distinct normal forms is
    locally confluent -- from `a` the fork to `b` and `c` rejoins at `c` via
    `b -> a -> c`, and from `b` the fork to `a` and `d` rejoins at `d` -- while
    `a` reduces to two distinct normal forms, so it is not confluent.

    So a True here is not a confluence result. Pair it with `is_terminating` to
    get one, or use `RewritingSystem.is_confluent`, which decides confluence
    directly.

    Meaningful only for a complete graph, for the reason given in
    `normal_forms`: a fork whose join sits past a truncation horizon looks like
    a fork that does not join.
    """
    reachable: dict[Node, set[Node]] = {}
    for n in trajectory.nodes:
        r_set: set[Node] = {n}
        q = deque([n])
        while q:
            curr = q.popleft()
            for child in trajectory.children(curr):
                if child not in r_set:
                    r_set.add(child)
                    q.append(child)
        reachable[n] = r_set

    for u in trajectory.nodes:
        children = list(trajectory.children(u))
        for i, v1 in enumerate(children):
            for v2 in children[i + 1:]:
                if not (reachable[v1] & reachable[v2]):
                    return False
    return True


def create_hyperset_rewrite_system() -> RewritingSystem:
    """Construct a canonical rewrite system operating directly over Hypersets."""
    rules = [
        RewriteRule(
            name="canonicalize",
            transform=lambda h: [h.canonical()] if len(h.apg.nodes) > len(h.canonical().apg.nodes) else [],
        ),
        RewriteRule(
            name="successor",
            transform=lambda h: [h.successor()] if h.is_well_founded and h.is_ordinal() and len(h) < 4 else [],
        ),
    ]
    return RewritingSystem(rules=rules, name="hyperset_calculus")
