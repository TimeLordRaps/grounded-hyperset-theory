# Grounded Hyperset Theory

[![CI](https://github.com/TimeLordRaps/grounded-hyperset-theory/actions/workflows/ci.yml/badge.svg)](https://github.com/TimeLordRaps/grounded-hyperset-theory/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Grounded Hyperset Theory** provides a Python reference implementation of non-well-founded set theory using Accessible Pointed Graphs (APGs), bisimulation equivalence, and constructive membership. It builds on the foundational graph structures and ordinal progressions formalized in [Hypermath](https://github.com/TimeLordRaps/hypermath) and [Ordinatics](https://github.com/TimeLordRaps/ordinatics), expanding into meta-features and bridges to formal calculi (meta-calculus, hyper-calculus, language calculus, and real analysis).

---

## 1. Overview

In classical Zermelo–Fraenkel set theory (ZFC), the Axiom of Foundation prohibits circular self-membership ($x \in x$) and requires all sets to be well-founded trees.

Grounded Hyperset Theory models sets under Aczel's Anti-Foundation Axiom (AFA), representing sets as **Accessible Pointed Graphs (APGs)**:
- Nodes represent set identity points.
- Directed edges represent membership dependencies.
- Bisimulation defines set identity: two graphs represent the exact same hyperset if and only if they are bisimilar.
- The **Quine atom** $\Omega = \{\Omega\}$ is modeled as a 1-cycle self-loop satisfying $\Omega \in \Omega$.

---

## 2. Meta-Features and Formal Calculi Pathways

Grounded Hyperset Theory establishes foundations for multiple formal calculi:

1. **Abstraction & Quotienting** (`abstraction.py`, `meta.py`):
   - Equivalence partitions (`NodePartition`), APG quotienting (`quotient_apg`), and hyperset quotienting (`quotient_hyperset`).
   - Forward simulation congruence checking (`is_congruence`) and bisimulation congruence checking (`is_bisimulation_congruence`).
   - Coarsest bisimulation refinement (`refine_to_bisimulation`) via signature grouping.
   - Depth-bounded k-horizon abstraction (`depth_abstraction`) and predicate abstraction (`predicate_abstraction`).
   - Strongly Connected Component condensation (`scc_quotient`, `scc_abstract_hyperset`) producing well-founded acyclic DAG projections of non-well-founded sets.
   - Objectification of relations, functions and APGs (`objectify_relation`, `objectify_function`, `objectify_apg`). Relations and functions round-trip exactly, and `deobjectify_function` refuses a multivalued relation. `objectify_apg` encodes the graph **up to isomorphism**: node ids become indices and labels are discarded, so the decoded graph is bisimilar to the original, not equal to it. `Abstraction.to_hyperset` is likewise lossy and has no inverse — the variable becomes a childless node, which is $\emptyset$, so nothing records where it occurred and `λx. x` and `λx. ∅` objectify identically.
   - Archetypal non-well-founded hypersets (`fractal_hyperset`, `meta_fractalize`, `unfold_step`). The four patterns name four **graphs** and denote **three** sets: `"sierpinski"` is the 3-cycle $A\to\{B,C\}$, $B\to\{A,C\}$, $C\to\{A,B\}$, on which the all-pairs relation is a bisimulation, so it quotients to $\Omega=\{\Omega\}$ and is a second drawing of `"quine"`. `"cantor_non_well_founded"` is not binary branching — $\{K,\emptyset\}$ and $\{\emptyset,K\}$ are one set. `meta_fractalize` iterates top-level expansion `depth` times and does not recurse into members.

2. **Meta-Calculus** (`meta_calculus.py`):
   - Symbolic dynamics of representational calculi: rewrite rules (`RewriteRule`) and transition systems (`RewritingSystem`, `RewriteSystem`).
   - State-transition trajectories modeled as Accessible Pointed Graphs (`reduction_apg`, `build_trajectory_apg`).
   - Dynamical bisimulation under Aczel's AFA (`trajectory_bisimilar`, `trajectory_quotient`).
   - Confluence verification (`is_confluent`), termination checks (`is_terminating`), normal forms (`normal_forms`), and periodic orbit detection (`find_periodic_orbits`).

3. **Hyper-Calculus** (`hyper_calculus.py`):
   - Group-theoretic transformations on APGs and Hypersets: permutations (`Permutation`) and permutation groups (`PermutationGroup`, `cyclic_group`).
   - Automorphism group computation on APGs (`automorphism_group`, `find_apg_automorphisms`, `APGAutomorphism`).
   - Group action orbits (`orbit`, `all_orbits`), stabilizers, and symmetry quotienting (`quotient_by_symmetry`, `orbit_quotient_apg`).
   - Invariance checks (`is_symmetric`, `is_invariant_under`, `symmetry_group_order`) and discrete transformation derivatives (`discrete_derivative`).

4. **Language Calculus** (`language_calculus.py`):
   - Formal syntax symbols, alphabets, and words (`Symbol`, `Alphabet`, `Word`).
   - Grammars and production rule dependency graphs (`ProductionRule`, `Grammar`, `SyntaxTree`, `derivation_step`, `grammar_bisimilar`).
   - Circular quotation trees and self-referential sentences (`liar_sentence`, `truth_teller_sentence`, `quine_syntax_term`, `self_referential_term`, `syntax_bisimilar`).
   - Python AST expression quotation and unquotation (`quote_syntax`, `unquote_syntax`).
   - Algebraic regular expressions (`Regex`), Brzozowski derivatives (`Regex.derivative`), and DFA state APGs (`dfa_apg`, `dfa_hyperset`).

5. **Real Analysis Bridge** (`real_analysis_bridge.py`, `math_calculus.py`):
   - Grounded signed integers (`GroundedInteger`, `hyperset_integer`) and exact rationals (`GroundedRational`, `hyperset_rational`) with full arithmetic and ordering.
   - Dedekind cuts (`DedekindCut`, `DedekindCutHyperset`) for real constants ($\sqrt{2}$, golden ratio $\phi$, rational cuts) with binary search interval bounding and numerical approximation.
   - Cauchy sequences (`CauchySequence`, `CauchySequenceHyperset`) for Euler's $e$, Leibniz $\pi$, and geometric series, with finite searches for a violation of the Cauchy criterion (`cauchy_violation`, `is_cauchy`) and for a difference between two sequences (`are_equivalent_cauchy`). These refute; they do not certify — a returned witness proves the property fails, and finding none over finitely many indices proves nothing.
   - Surreal numbers (`SurrealNumber`, `SurrealHyperset`) with Conway's order and the simplicity rule, over the dyadic rationals. Options are stored in finite tuples, so every representable value has finite birthday and is a dyadic rational: this does **not** reach the infinitesimals or the transfinite surreals, both of which need infinite option sets. `surreal_infinitesimal(d)` is the finite approximant $1/2^{d+1}$ and `surreal_omega(d)` is the integer $d+1$; `is_infinitesimal()` and `is_infinite()` are correspondingly False throughout.
   - Classical calculus reachability: central difference quotients (`derivative_quotient`, `hyperset_derivative_sequence`), definite Riemann integrals (`riemann_integral`), and exact rational polynomial differentiation and integration (`symbolic_polynomial_derivative`, `symbolic_polynomial_integral`).

---

## 3. Quickstart

```python
from grounded_hyperset_theory import EmptyHyperset, QuineAtom, Hyperset, bisimilar

# 1. Empty set ∅
empty = EmptyHyperset()
print(empty.is_well_founded)  # True

# 2. Quine atom Ω = {Ω}
omega = QuineAtom()
print(omega in omega)         # True (circular self-membership)
print(omega.is_well_founded)  # False

# 3. Bisimulation equivalence
# A 2-cycle a = {b}, b = {a} is bisimilar to the 1-cycle Ω = {Ω}
from grounded_hyperset_theory import Node, AccessiblePointedGraph

a, b = Node("a"), Node("b")
two_cycle_apg = AccessiblePointedGraph(root=a, edges={a: [b], b: [a]})
two_cycle_set = Hyperset(two_cycle_apg)

print(two_cycle_set == omega)  # True!

# 4. Self-referential syntax (Liar sentence L = not(L))
from grounded_hyperset_theory import liar_sentence, self_referential_term, syntax_bisimilar

l1 = liar_sentence()
l2 = self_referential_term("La", {"La": ("not", ["Lb"]), "Lb": ("not", ["La"])})
print(syntax_bisimilar(l1, l2))  # True (bisimilar under Aczel's AFA)

# 5. Real analysis bridge (Dedekind cuts & Cauchy sequences)
from grounded_hyperset_theory import DedekindCut, CauchySequence, GroundedRational

sqrt2 = DedekindCut.sqrt_two()
print(sqrt2.contains(GroundedRational(14, 10)))  # True (1.4 < √2)
print(sqrt2.contains(GroundedRational(15, 10)))  # False (1.5 > √2)
print(round(sqrt2.approximate(), 4))            # 1.4142

seq_e = CauchySequence.euler_e()
print(round(seq_e.limit_approx(8), 5))          # 2.71828
```

---

## 4. Development and Testing

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/check_presentation.py
python -S -c "import sys; sys.path.insert(0, 'src'); import grounded_hyperset_theory; print(grounded_hyperset_theory.__version__)"
python -m build
python -m twine check dist/*
python scripts/check_release_boundary.py dist/*
```

---

## 5. License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
