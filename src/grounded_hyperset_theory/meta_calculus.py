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
        """Apply this rule to state, returning all valid next states."""
        try:
            return list(self.transform(state))
        except Exception:
            return []

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
        """Apply the first matching rule and return the first result, or None if in normal form."""
        for r in self.rules:
            nxt = r.apply(state)
            if nxt:
                return nxt[0]
        return None

    def trace(self, initial_state: Hyperset, max_steps: int = 100) -> list[Hyperset]:
        """Generate a deterministic sequential execution trace from the initial state."""
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
        """Construct the transition state APG rooted at initial_state.

        Nodes in the APG correspond to unique states modulo bisimulation.
        Edges represent valid rewrite transitions between states.
        """
        states: list[Hyperset] = [initial_state]
        state_to_node: dict[int, Node] = {0: Node(0, label="s0")}
        edges: dict[Node, set[Node]] = {state_to_node[0]: set()}

        queue: deque[tuple[int, int]] = deque([(0, 0)])

        while queue:
            curr_idx, depth = queue.popleft()
            if depth >= max_depth:
                continue

            curr_state = states[curr_idx]
            curr_node = state_to_node[curr_idx]

            for next_state in self.step(curr_state):
                existing_idx = None
                for idx, s in enumerate(states):
                    if s == next_state:
                        existing_idx = idx
                        break

                if existing_idx is None:
                    if len(states) >= max_states:
                        continue
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
        """Find terminal states (normal forms) or cyclic attractors in the rewrite dynamics."""
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
        """Check the local confluence (diamond property) of reachable states."""
        apg = self.reduction_apg(start, max_depth=max_depth, max_states=max_states)
        for u in apg.nodes:
            children = list(apg.children(u))
            for i, v1 in enumerate(children):
                for v2 in children[i + 1:]:
                    desc1 = self._descendants(apg, v1)
                    desc2 = self._descendants(apg, v2)
                    if not (desc1 & desc2):
                        return False
        return True

    @staticmethod
    def _descendants(apg: AccessiblePointedGraph, start: Node) -> set[Node]:
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
) -> bool:
    """Determine whether two trajectories (or systems) are bisimilar under Aczel's AFA."""
    if isinstance(traj1, RewriteTrajectory) and isinstance(traj2, RewriteTrajectory):
        return bisimilar(traj1.to_apg(), traj2.to_apg())

    if isinstance(traj1, RewritingSystem) and isinstance(traj2, RewritingSystem):
        if init1 is None or init2 is None:
            raise ValueError("init1 and init2 required when comparing RewritingSystems")
        g1 = traj1.reduction_apg(init1, max_states=max_states)
        g2 = traj2.reduction_apg(init2, max_states=max_states)
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
    """Identify all terminal normal forms in a trajectory."""
    return frozenset(n for n in trajectory.nodes if len(trajectory.children(n)) == 0)


def is_terminating(trajectory: AccessiblePointedGraph) -> bool:
    """Return True if the trajectory APG is acyclic, proving guaranteed termination."""
    return not trajectory.has_cycles()


def find_periodic_orbits(trajectory: AccessiblePointedGraph) -> list[list[Node]]:
    """Detect all simple cycles in a trajectory APG."""
    cycles: list[list[Node]] = []
    visited: set[Node] = set()
    stack: list[Node] = []
    stack_set: set[Node] = set()

    def dfs(curr: Node) -> None:
        visited.add(curr)
        stack.append(curr)
        stack_set.add(curr)

        for nxt in sorted(trajectory.children(curr), key=lambda x: str(x.id)):
            if nxt in stack_set:
                cycle_start = stack.index(nxt)
                cycle = stack[cycle_start:]
                min_idx = min(range(len(cycle)), key=lambda i: str(cycle[i].id))
                norm_cycle = cycle[min_idx:] + cycle[:min_idx]
                if norm_cycle not in cycles:
                    cycles.append(norm_cycle)
            elif nxt not in visited:
                dfs(nxt)

        stack.pop()
        stack_set.remove(curr)

    dfs(trajectory.root)
    return cycles


def is_locally_confluent(trajectory: AccessiblePointedGraph) -> bool:
    """Test the local confluence on a trajectory APG."""
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
