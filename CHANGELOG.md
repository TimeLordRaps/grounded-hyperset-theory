# Changelog

## 0.2.0 - 2026-09-17

Expanded scope with meta-features and pathways to formal calculi:

- **Abstraction & Quotienting** (`abstraction.py`, `meta.py`):
  - Equivalence partitions (`NodePartition`), APG quotienting (`quotient_apg`), and hyperset quotienting (`quotient_hyperset`).
  - Forward simulation congruence checking (`is_congruence`), bisimulation congruence checking (`is_bisimulation_congruence`), and Paige-Tarjan coarsest bisimulation refinement (`refine_to_bisimulation`).
  - Depth-bounded k-horizon abstraction (`depth_abstraction`, `depth_abstract_hyperset`) with horizon edge truncation.
  - Predicate abstraction (`predicate_abstraction`, `predicate_abstract_hyperset`) over arbitrary boolean node classifiers.
  - Tarjan Strongly Connected Component condensation (`scc_quotient`, `scc_abstract_hyperset`) producing well-founded acyclic DAG projections of non-well-founded sets.
  - Lambda abstraction and variable instantiation (`Abstraction`, `abstract`).
  - First-class objectification and deobjectification of relations, functions, and APGs (`objectify_relation`, `deobjectify_relation`, `objectify_function`, `deobjectify_function`, `objectify_apg`, `deobjectify_apg`).
  - Archetypal fractal hypersets (`fractal_hyperset`, `meta_fractalize`, `unfold_step`).
- **Meta-Calculus** (`meta_calculus.py`):
  - Symbolic dynamics of symbolic representational calculi: rewrite rules (`RewriteRule`), rewriting systems (`RewritingSystem`, `RewriteSystem`).
  - State-transition graph generation as Accessible Pointed Graphs (`reduction_apg`, `build_trajectory_apg`).
  - Trajectory wrapping as first-class hypersets (`trajectory_hyperset`, `RewriteTrajectory`).
  - Dynamical bisimulation under Aczel's AFA (`trajectory_bisimilar`, `trajectory_quotient`).
  - Termination checking (`is_terminating`), normal forms (`normal_forms`), periodic orbits and limit cycles (`find_periodic_orbits`), local confluence (`is_confluent`, `is_locally_confluent`).
- **Hyper-Calculus** (`hyper_calculus.py`):
  - Group-theoretic transformations on APGs and Hypersets: permutations (`Permutation`), groups (`PermutationGroup`, `cyclic_group`, `trivial_group`).
  - Pointed and structural APG automorphism computation (`automorphism_group`, `find_apg_automorphisms`, `find_hyperset_automorphisms`, `APGAutomorphism`).
  - Group action orbits (`orbit`, `all_orbits`), stabilizers, and orbit quotienting (`quotient_by_symmetry`, `orbit_quotient_apg`, `orbit_quotient_hyperset`).
  - Invariance verification (`is_symmetric`, `is_invariant_under`, `symmetry_group_order`).
  - Discrete differential / difference forms on hypersets (`discrete_derivative`).
- **Language Calculus** (`language_calculus.py`):
  - Formal syntax symbols, alphabets, and words (`Symbol`, `Alphabet`, `Word`).
  - Grammars and production rule dependency APGs (`ProductionRule`, `Grammar`, `SyntaxTree`, `derivation_step`, `grammar_bisimilar`).
  - Self-referential quotation trees and circular sentences (`liar_sentence`, `truth_teller_sentence`, `quine_syntax_term`, `self_referential_term`, `syntax_bisimilar`).
  - Python AST/expression quotation and unquotation (`quote_syntax`, `unquote_syntax`).
  - Algebraic regular language expressions (`Regex`), Brzozowski derivatives (`Regex.derivative`), and DFA state APGs (`dfa_apg`, `dfa_hyperset`).
- **Real Analysis Bridge** (`real_analysis_bridge.py`, `math_calculus.py`):
  - Grounded signed integers (`GroundedInteger`, `hyperset_integer`, `hyperset_to_integer`) and exact rationals (`GroundedRational`, `hyperset_rational`, `hyperset_to_rational`) with full arithmetic and ordering.
  - Dedekind cuts (`DedekindCut`, `DedekindCutHyperset`) for real constants ($\sqrt{2}$, golden ratio $\phi$, rational cuts) with binary search bounding intervals and float approximations.
  - Cauchy sequences (`CauchySequence`, `CauchySequenceHyperset`) for Euler's $e$, Leibniz $\pi$, and geometric series, with Cauchy convergence tests and sequence equivalence (`are_equivalent_cauchy`).
  - Surreal numbers (`SurrealNumber`, `SurrealHyperset`) and nonstandard infinitesimals (`SurrealNumber.infinitesimal`, `surreal_infinitesimal`, `surreal_omega`).
  - Classical calculus reachability: central difference quotients (`derivative_quotient`, `hyperset_derivative_sequence`), definite Riemann integrals (`riemann_integral`), and exact rational polynomial differentiation and integration (`symbolic_polynomial_derivative`, `symbolic_polynomial_integral`).

## 0.1.0 - 2026-08-20

Initial release:

- Accessible Pointed Graphs (APGs) with root-reachability pruning, cycle detection, topological sorting, and subgraph extraction.
- Aczel's Anti-Foundation Axiom (AFA) and bisimulation equivalence for non-well-founded sets.
- Canonical strongly extensional bisimulation quotient graph minimization.
- Hypersets with constructive membership (`contains`, `__contains__`), bisimilar equality (`__eq__`), and empty set representations.
- Canonical Quine atom $\Omega = \{\Omega\}$ and Aczel Solution Lemma system solver (`solve_system`).
- Set operations: constructive union (`union`, `|`), intersection (`intersection`, `&`), difference (`difference`, `-`), and subset relations (`<=`, `<`, `>=`, `>`).
- Pure von Neumann ordinal arithmetic and transitive set verification (`von_neumann_ordinal`, `successor`, `is_transitive`, `is_ordinal`).
- Kuratowski ordered pairs (`pair`).
- Zero required runtime dependencies (`dependencies = []`).
