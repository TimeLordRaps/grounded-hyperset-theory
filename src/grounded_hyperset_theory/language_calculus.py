"""Formal syntax, terms, alphabets, productions, and quotation trees as grounded hypersets."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Hashable, Iterable, Mapping, Sequence

from .graph import AccessiblePointedGraph, Node
from .hyperset import EmptyHyperset, Hyperset, bisimilar, pair, von_neumann_ordinal
from .meta import _unpack_pair


@dataclass(frozen=True)
class Symbol:
    """A grammar symbol (terminal or nonterminal)."""

    name: str
    is_terminal: bool = True

    def to_hyperset(self) -> Hyperset:
        """Ground symbol into a tagged hyperset."""
        root = Node(f"sym_{self.name}", label=self.name)
        kind = Node(0 if self.is_terminal else 1)
        return Hyperset(AccessiblePointedGraph(root=root, edges={root: [kind], kind: []}))

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        kind = "T" if self.is_terminal else "NT"
        return f"Symbol({self.name!r}, {kind})"


class Alphabet:
    """A finite collection of language symbols."""

    def __init__(self, symbols: Iterable[Symbol | str]) -> None:
        sym_list: list[Symbol] = []
        for s in symbols:
            if isinstance(s, Symbol):
                sym_list.append(s)
            else:
                sym_list.append(Symbol(str(s), is_terminal=True))
        self._symbols = tuple(sym_list)
        self._symbol_set = frozenset(self._symbols)
        self._name_set = frozenset(s.name for s in self._symbols)

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, Symbol):
            return item in self._symbol_set
        if isinstance(item, str):
            return item in self._name_set
        return False

    def __len__(self) -> int:
        return len(self._symbol_set)

    def __iter__(self):
        return iter(self._symbols)

    def to_hyperset(self) -> Hyperset:
        """Objectify alphabet into a Hyperset of symbol hypersets."""
        return Hyperset.from_elements(*(s.to_hyperset() for s in self._symbols))

    def __repr__(self) -> str:
        return f"Alphabet({list(self._symbols)})"


class Word:
    """A finite sequence of symbols forming a string or sentence."""

    def __init__(self, symbols: Sequence[Symbol | str]) -> None:
        self.symbols = tuple(s if isinstance(s, Symbol) else Symbol(str(s)) for s in symbols)

    @classmethod
    def from_str(cls, s: str) -> Word:
        """Construct a word from a string of characters."""
        return cls([Symbol(ch, is_terminal=True) for ch in s])

    def __len__(self) -> int:
        return len(self.symbols)

    def __str__(self) -> str:
        return "".join(s.name for s in self.symbols)

    def to_hyperset(self) -> Hyperset:
        """Encode word into nested Kuratowski pairs."""
        curr = EmptyHyperset()
        for sym in reversed(self.symbols):
            curr = pair(sym.to_hyperset(), curr)
        return curr

    def __repr__(self) -> str:
        return f"Word({str(self)!r})"


@dataclass(frozen=True)
class ProductionRule:
    """A grammar production rule: lhs -> rhs."""

    lhs: Symbol
    rhs: tuple[Symbol, ...]

    def __init__(
        self,
        lhs: Symbol | str | None = None,
        rhs: Sequence[Symbol | str] | None = None,
        *,
        head: Symbol | str | None = None,
        body: Sequence[Symbol | str] | None = None,
    ) -> None:
        actual_lhs = lhs if lhs is not None else head
        actual_rhs = rhs if rhs is not None else body
        if actual_lhs is None:
            raise ValueError("ProductionRule requires lhs or head")
        if actual_rhs is None:
            actual_rhs = ()

        s_lhs = actual_lhs if isinstance(actual_lhs, Symbol) else Symbol(str(actual_lhs), is_terminal=False)
        s_rhs = tuple(s if isinstance(s, Symbol) else Symbol(str(s)) for s in actual_rhs)

        object.__setattr__(self, "lhs", s_lhs)
        object.__setattr__(self, "rhs", s_rhs)

    @property
    def head(self) -> str:
        return self.lhs.name

    @property
    def body(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.rhs)

    def to_hyperset(self) -> Hyperset:
        """Ground production rule into a Hyperset pair (lhs, rhs_word)."""
        rhs_word = Word(self.rhs).to_hyperset()
        return pair(self.lhs.to_hyperset(), rhs_word)

    def __repr__(self) -> str:
        rhs_str = " ".join(s.name for s in self.rhs) if self.rhs else "ε"
        return f"{self.lhs.name} -> {rhs_str}"


class Grammar:
    """A formal grammar with variables, terminals, productions, and a start symbol."""

    def __init__(
        self,
        variables: Sequence[Symbol],
        terminals: Sequence[Symbol],
        productions: Sequence[ProductionRule],
        start: Symbol,
    ) -> None:
        self.variables = tuple(variables)
        self.terminals = tuple(terminals)
        self.productions = tuple(productions)
        self.start = start

    def to_hyperset(self) -> Hyperset:
        """Ground the entire grammar into a Hyperset (start, productions)."""
        prod_hypersets = [p.to_hyperset() for p in self.productions]
        p_set = Hyperset.from_elements(*prod_hypersets)
        return pair(self.start.to_hyperset(), p_set)

    def grammar_apg(self) -> AccessiblePointedGraph:
        """Construct the dependency APG of the grammar rooted at the start symbol."""
        root_node = Node(self.start.name, label=self.start.name)
        node_map: dict[str, Node] = {self.start.name: root_node}

        for nt in self.variables:
            if nt.name not in node_map:
                node_map[nt.name] = Node(nt.name, label=nt.name)
        for t in self.terminals:
            if t.name not in node_map:
                node_map[t.name] = Node(t.name, label=t.name)

        edges: dict[Node, set[Node]] = {n: set() for n in node_map.values()}
        for p in self.productions:
            p_node = node_map[p.lhs.name]
            for s in p.rhs:
                if s.name in node_map:
                    edges[p_node].add(node_map[s.name])

        return AccessiblePointedGraph(root=root_node, edges=edges)

    def is_recursive(self) -> bool:
        return self.grammar_apg().has_cycles()


FormalGrammar = Grammar


@dataclass(frozen=True)
class SyntaxTree:
    """An abstract syntax tree with node label and children trees."""

    label: str
    children: tuple[SyntaxTree, ...] = ()

    def __init__(self, label: str, children: Sequence[SyntaxTree] = ()) -> None:
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "children", tuple(children))

    def to_hyperset(self) -> Hyperset:
        """Ground this syntax tree into a Hyperset APG."""
        root = Node("tree_root", label=self.label)
        edges: dict[Node, set[Node]] = {root: set()}

        def build(tree: SyntaxTree, parent: Node, counter: list[int]) -> None:
            for c in tree.children:
                counter[0] += 1
                c_node = Node(f"node_{counter[0]}", label=c.label)
                edges[parent].add(c_node)
                edges[c_node] = set()
                build(c, c_node, counter)

        build(self, root, [0])
        return Hyperset(AccessiblePointedGraph(root=root, edges=edges))

    def __repr__(self) -> str:
        if not self.children:
            return self.label
        return f"{self.label}({', '.join(repr(c) for c in self.children)})"


def derivation_step(tree: SyntaxTree, rule: ProductionRule) -> list[SyntaxTree]:
    """Perform one derivation step on a syntax tree matching rule."""
    if tree.label == rule.lhs.name and not tree.children:
        # Expand this leaf
        new_children = tuple(SyntaxTree(s.name) for s in rule.rhs)
        return [SyntaxTree(tree.label, children=new_children)]

    results: list[SyntaxTree] = []
    for i, child in enumerate(tree.children):
        sub_steps = derivation_step(child, rule)
        for s in sub_steps:
            new_c = list(tree.children)
            new_c[i] = s
            results.append(SyntaxTree(tree.label, children=new_c))
    return results


def quote_syntax(expr: Any) -> Hyperset:
    """Quote arbitrary nested Python syntax (tuples, ints, strings) into a grounded Hyperset."""
    if isinstance(expr, int):
        # Tag 0: int ordinal
        tag = von_neumann_ordinal(0)
        val = von_neumann_ordinal(abs(expr))
        return pair(tag, val)
    elif isinstance(expr, str):
        # Tag 1: string
        tag = von_neumann_ordinal(1)
        return pair(tag, string_to_hyperset(expr))
    elif isinstance(expr, tuple):
        # Tag 2: tuple
        tag = von_neumann_ordinal(2)
        curr = EmptyHyperset()
        for elem in reversed(expr):
            curr = pair(quote_syntax(elem), curr)
        return pair(tag, curr)
    else:
        # Fallback: empty hyperset
        return EmptyHyperset()


def unquote_syntax(h: Hyperset) -> Any:
    """Unquote a grounded Hyperset back into native Python syntax structures."""
    try:
        tag_h, payload = _unpack_pair(h)
    except Exception:
        return ()

    tag = tag_h.to_int()
    if tag == 0:
        return payload.to_int()
    elif tag == 1:
        # String
        chars: list[str] = []
        curr = payload
        while not curr.is_empty:
            try:
                char_h, curr = _unpack_pair(curr)
                # char_h is pair(1, ord)
                _, ord_h = _unpack_pair(char_h)
                chars.append(chr(ord_h.to_int()))
            except Exception:
                break
        return "".join(chars)
    elif tag == 2:
        # Tuple
        items: list[Any] = []
        curr = payload
        while not curr.is_empty:
            try:
                item_h, curr = _unpack_pair(curr)
                items.append(unquote_syntax(item_h))
            except Exception:
                break
        return tuple(items)
    return ()


def symbol_to_hyperset(sym: str | Hashable) -> Hyperset:
    """Encode a discrete alphabet symbol into a canonical grounded Hyperset."""
    val = ord(sym[0]) if isinstance(sym, str) and len(sym) > 0 else hash(sym) & 0xFFFF
    return pair(von_neumann_ordinal(1), von_neumann_ordinal(val))


def string_to_hyperset(s: str) -> Hyperset:
    """Encode a finite string as an ordered nested Kuratowski list of character ordinals."""
    curr = EmptyHyperset()
    for ch in reversed(s):
        curr = pair(symbol_to_hyperset(ch), curr)
    return curr


SyntaxTerm = SyntaxTree


def self_referential_term(
    root_id: str,
    rules: Mapping[str, tuple[str, Iterable[str]]],
) -> Hyperset:
    """Construct a self-referential / circular syntax quotation tree under Aczel's AFA."""
    node_map: dict[str, Node] = {
        var: Node(var, label=label)
        for var, (label, _) in rules.items()
    }
    if root_id not in node_map:
        raise KeyError(f"Root identifier {root_id} not found in rules.")

    edges: dict[Node, set[Node]] = {}
    for var, (_, children) in rules.items():
        parent_node = node_map[var]
        edges[parent_node] = {node_map[c] for c in children if c in node_map}

    return Hyperset(AccessiblePointedGraph(root=node_map[root_id], edges=edges))


def liar_sentence() -> Hyperset:
    """The canonical Liar sentence: L = not(L)."""
    l_node = Node("L", label="not")
    return Hyperset(AccessiblePointedGraph(root=l_node, edges={l_node: [l_node]}))


def truth_teller_sentence() -> Hyperset:
    """The canonical Truth-teller sentence: T = true(T)."""
    t_node = Node("T", label="true")
    return Hyperset(AccessiblePointedGraph(root=t_node, edges={t_node: [t_node]}))


def quine_syntax_term() -> Hyperset:
    """The canonical Quine quotation sentence: Q = quote(Q)."""
    q_node = Node("Q", label="quote")
    return Hyperset(AccessiblePointedGraph(root=q_node, edges={q_node: [q_node]}))


def syntax_bisimilar(term1: Hyperset, term2: Hyperset) -> bool:
    """Determine whether two quotation trees / syntax hypersets are bisimilar under Aczel's AFA."""
    return bisimilar(term1.apg, term2.apg)


def grammar_bisimilar(g1: Grammar, g2: Grammar) -> bool:
    """Check whether two grammars have bisimilar structural production dependencies under Aczel's AFA."""
    return bisimilar(g1.grammar_apg(), g2.grammar_apg())


# Regular language calculus with Brzozowski derivatives

def _union_operands(regex: Regex) -> tuple[Regex, ...]:
    """The operands of a union, flattened through nesting; a non-union alone."""
    if regex.kind == "union" and regex.left is not None and regex.right is not None:
        return _union_operands(regex.left) + _union_operands(regex.right)
    return (regex,)


def _regex_sort_key(regex: Regex) -> tuple:
    """A total order on expressions, so a union has one canonical arrangement.

    Structural rather than textual: ``repr`` on an unnormalised expression can be
    thousands of levels deep, which is how ``dfa_apg`` used to raise
    RecursionError while labelling a node.
    """
    return (
        regex.kind,
        regex.val or "",
        _regex_sort_key(regex.left) if regex.left is not None else (),
        _regex_sort_key(regex.right) if regex.right is not None else (),
    )


@dataclass(frozen=True)
class Regex:
    """Algebraic regular expression for Brzozowski language calculus.

    Unions are kept in a canonical ACI-normalised form -- see ``union`` -- which
    is what makes the set of derivatives finite and ``dfa_apg`` terminate.
    """

    kind: str  # 'empty', 'eps', 'lit', 'union', 'concat', 'star'
    val: str | None = None
    left: Regex | None = None
    right: Regex | None = None

    @classmethod
    def empty(cls) -> Regex:
        return cls("empty")

    @classmethod
    def eps(cls) -> Regex:
        return cls("eps")

    @classmethod
    def lit(cls, ch: str) -> Regex:
        return cls("lit", val=ch)

    def union(self, other: Regex) -> Regex:
        """Union, normalised modulo associativity, commutativity and idempotence.

        Brzozowski's theorem gives a *finite* set of derivatives only modulo
        these three. Keeping ``a|b`` and ``b|a`` apart, or ``(a|b)|c`` and
        ``a|(b|c)``, makes the derivative set infinite and ``dfa_apg`` diverge:
        ``(a|b)*ab(a|b)*`` has a three-state minimal DFA and used to produce 65
        states at a budget of 64, 257 at 256, without ever settling.

        Operands are flattened out of nested unions, ``empty`` operands dropped,
        duplicates removed and the remainder sorted, so two unions of the same
        operand set are the same object and become the same DFA state.
        """
        operands: list[Regex] = []
        for operand in _union_operands(self) + _union_operands(other):
            if operand.kind == "empty":
                continue
            if operand not in operands:
                operands.append(operand)
        if not operands:
            return Regex.empty()
        operands.sort(key=_regex_sort_key)
        result = operands[-1]
        for operand in reversed(operands[:-1]):
            result = Regex("union", left=operand, right=result)
        return result

    def concat(self, other: Regex) -> Regex:
        if self.kind == "empty" or other.kind == "empty":
            return Regex.empty()
        if self.kind == "eps":
            return other
        if other.kind == "eps":
            return self
        return Regex("concat", left=self, right=other)

    def star(self) -> Regex:
        if self.kind in ("empty", "eps"):
            return Regex.eps()
        if self.kind == "star":
            return self
        return Regex("star", left=self)

    @property
    def is_nullable(self) -> bool:
        if self.kind == "eps" or self.kind == "star":
            return True
        if self.kind in ("empty", "lit"):
            return False
        if self.kind == "union":
            return bool(self.left and self.left.is_nullable) or bool(self.right and self.right.is_nullable)
        if self.kind == "concat":
            return bool(self.left and self.left.is_nullable) and bool(self.right and self.right.is_nullable)
        return False

    def derivative(self, a: str) -> Regex:
        if self.kind == "empty" or self.kind == "eps":
            return Regex.empty()
        if self.kind == "lit":
            return Regex.eps() if self.val == a else Regex.empty()
        if self.kind == "union":
            assert self.left and self.right
            return self.left.derivative(a).union(self.right.derivative(a))
        if self.kind == "concat":
            assert self.left and self.right
            term1 = self.left.derivative(a).concat(self.right)
            if self.left.is_nullable:
                return term1.union(self.right.derivative(a))
            return term1
        if self.kind == "star":
            assert self.left
            return self.left.derivative(a).concat(self.star())
        return Regex.empty()

    def __repr__(self) -> str:
        if self.kind == "empty":
            return "∅"
        if self.kind == "eps":
            return "ε"
        if self.kind == "lit":
            return str(self.val)
        if self.kind == "union":
            return f"({self.left} | {self.right})"
        if self.kind == "concat":
            return f"({self.left} . {self.right})"
        if self.kind == "star":
            return f"({self.left})*"
        return super().__repr__()


def dfa_apg(regex: Regex, alphabet: Iterable[str], max_states: int = 64) -> AccessiblePointedGraph:
    """The derivative automaton of ``regex`` over ``alphabet``, as an APG.

    States are derivatives of ``regex`` under ACI normalisation, which by
    Brzozowski's theorem is a finite set, and only reachable states are built.
    That is **not** the same as minimal: two reachable states can denote the same
    language and stay distinct. Measured, ``(a*b*)*`` produces three states for a
    language whose minimal DFA has one, and ``(a|b)*ab(a|b)*`` produces six where
    three suffice. Minimisation is a separate pass and is not done here; this
    docstring used to claim "minimal" and that was wrong.

    Every state gets a transition for every letter, so the result is a complete
    automaton or there is no result at all.

    Raises:
        ValueError: if the automaton needs more than ``max_states`` states.
            Truncating instead would return something that is not an automaton:
            the states still queued would have no outgoing transitions, which
            reads exactly like states that reject every continuation. That is
            what it used to do, silently -- and because the budget was tested
            once per dequeued state while the inner loop inserted freely, the
            count came back over the cap as well, 65 states for ``max_states=64``.
    """
    if max_states < 1:
        raise ValueError(f"max_states must be at least 1, got {max_states}")

    alpha = list(alphabet)
    root_node = Node(0, label=str(regex))
    state_map: dict[Regex, Node] = {regex: root_node}
    edges: dict[Node, set[Node]] = {root_node: set()}
    queue: deque[Regex] = deque([regex])
    next_id = 1

    while queue:
        curr_reg = queue.popleft()
        curr_node = state_map[curr_reg]

        for a in alpha:
            deriv = curr_reg.derivative(a)
            if deriv not in state_map:
                if len(state_map) >= max_states:
                    raise ValueError(
                        f"the derivative automaton of {regex!r} over "
                        f"{sorted(alpha)} needs more than max_states="
                        f"{max_states} states; raise the budget rather than "
                        f"accepting a partial automaton, which would be missing "
                        f"transitions and so would reject words in the language"
                    )
                deriv_node = Node(next_id, label=str(deriv))
                next_id += 1
                state_map[deriv] = deriv_node
                edges[deriv_node] = set()
                queue.append(deriv)
            edges[curr_node].add(state_map[deriv])

    return AccessiblePointedGraph(root=root_node, edges=edges)


def dfa_hyperset(regex: Regex, alphabet: Iterable[str], max_states: int = 64) -> Hyperset:
    """Ground the derivative automaton of ``regex`` into a Hyperset.

    See ``dfa_apg``: reachable states only, complete transitions, and a refusal
    rather than a truncation when the budget is not enough.
    """
    return Hyperset(dfa_apg(regex, alphabet, max_states=max_states))
