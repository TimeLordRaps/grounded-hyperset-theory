# AGENTS.md

Working rules for automated contributors to Grounded Hyperset Theory. Read this before editing anything.

## 0. Before you touch anything

High-risk couplings are enforced by CI and presentation gates. Check this table first.

| If you are changing... | You must also... |
|---|---|
| the version, anywhere | bump all five: `pyproject.toml`, `src/grounded_hyperset_theory/__init__.py`, `CITATION.cff`, `.zenodo.json`, and a dated `## X.Y.Z - YYYY-MM-DD` heading in `CHANGELOG.md` |
| dependencies | keep `dependencies = []` in `pyproject.toml`. Pure stdlib smoke (`python -S`) enforces zero required runtime dependencies on base import paths |
| public presentation surfaces | run `python scripts/check_presentation.py` to ensure zero private path leaks, valid local links, and uncompromised boundary claims |
| line endings | keep LF line endings across text files; `.gitattributes` forces `eol=lf` |

Then, before you propose the change:

```bash
python -m pytest -q
python scripts/check_presentation.py
```

## 1. What this repository is

Grounded Hyperset Theory is a **verification-grade reference implementation of non-well-founded set theory** based on Accessible Pointed Graphs (APGs), bisimulation equivalence, and constructive membership under Aczel's Anti-Foundation Axiom (AFA). It bridges non-well-founded sets into foundational formal calculi:

1. **Abstraction & Quotienting:** Equivalence partitions (`NodePartition`), APG quotienting (`quotient_apg`), coarsest bisimulation refinement by iterated signature grouping (`refine_to_bisimulation`), and Tarjan Strongly Connected Component DAG condensation (`scc_quotient`).
2. **Meta-Calculus:** Rewrite systems (`RewriteSystem`), transition trajectories as APGs, confluence verification, dynamical bisimulation, and periodic orbit detection.
3. **Hyper-Calculus:** Permutation groups, APG and hyperset automorphisms (`find_apg_automorphisms`), symmetry orbits, and discrete difference derivatives.
4. **Language Calculus:** Formal grammars, self-referential liar sentences (`liar_sentence`), quotation trees, AST quotation, and regular language derivatives.
5. **Real Analysis Bridge:** Grounded signed integers, exact rationals, Dedekind cuts (`DedekindCut.sqrt_two`), Cauchy sequences, and Surreal numbers under Conway's order and simplicity rule. The surreals here are the **dyadic rationals only**: options live in finite tuples, so every value has finite birthday. Infinitesimals and transfinite surreals need infinite option sets and are out of reach — `surreal_infinitesimal(d)` is $1/2^{d+1}$ and `surreal_omega(d)` is the integer $d+1$. Do not reintroduce a claim that either is reached.

### 1.1 Ecosystem Relations

This repository is an integral component of the TimeLord formal mathematics ecosystem:
- `hypermath`: primitive foundational algebraic kernel, quadrilateral filtration, Lean 4 bridge.
- `ordinatics`: ordinal arithmetic, Veblen hierarchies, and transfinite stage semantics.
- `grounded-hypercalculi`: Oracle, Language, Meta, Hyper, Ordinal, and Real Calculi.
- `verifier` (`vstd`): portable, bounded, refutable evidence standard and reference implementation.

## 2. Prime directive

> Changes that strengthen a claim without stronger evidence are non-conforming.

An uncertain, non-bisimilar, non-confluent, or refuting result is frequently the **correct** result. Never:
- turn non-bisimilar graphs into bisimilar sets without valid relation witnesses;
- mask cycles in acyclic assertions;
- claim confluence when critical pairs fail to join;
- introduce third-party runtime dependencies into base import paths.

## 3. Environment and commands

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/check_presentation.py
python -m compileall -q src scripts tests
```

Stdlib-purity smoke (zero third-party dependencies required for base imports):

```bash
PYTHONPATH=src python -S -c "import grounded_hyperset_theory; print(grounded_hyperset_theory.__version__)"
```

Reproducible release checks:

```bash
VERSION="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
python scripts/release_artifacts.py build --ref HEAD --release "$VERSION" --output-dir dist/release-integrity
python scripts/release_artifacts.py verify "dist/release-integrity/grounded-hyperset-theory-$VERSION.manifest.json"
python -m twine check dist/release-integrity/*.whl dist/release-integrity/*.tar.gz
python scripts/check_release_boundary.py dist/release-integrity/*.zip dist/release-integrity/*.whl dist/release-integrity/*.tar.gz
python scripts/check_installed_wheel.py --wheel-dir dist/release-integrity
```

## 4. Conventions

Every substantive module begins with `from __future__ import annotations`. All parameters and return types are annotated. Hypersets and APGs maintain mathematical immutability and constructive membership.

`requires-python = ">=3.10"`, with automated CI matrices testing Python 3.10, 3.11, 3.12, and 3.13 on both Ubuntu and Windows.

## 5. Change process

Work lands via pull request into `main`. Commits are GPG-signed (`git commit -S`). Never pass `--no-gpg-sign`.
Release tags follow `v*` (e.g. `v0.2.0`) and trigger automated OIDC Trusted Publishing to PyPI only after full conformance-gate and artifact attestation pass.

## 6. Test skip disclosure and rubric classification

To prevent skip slippage, automated contributors and maintainers MUST disclose the
explicit rationale behind every skipped test or unrun check. Skips must clear a
standard checklist of rubricized definitional categories:

1. `OS_CAPABILITY_GUARD`: Underlying operating system capability absent.
2. `OPTIONAL_DEPENDENCY_ABSENT`: Non-core third-party dependency or optional extra not installed.
3. `EXTERNAL_SERVICE_BOUNDARY`: Live network service, external API, or daemon unavailable.
4. `ARCHITECTURAL_PLATFORM_UNSUPPORTED`: Processor architecture or endianness unsupported.
5. `HARDWARE_DEVICE_UNAVAILABLE`: Physical accelerator or specialized hardware absent.
6. `PRIVILEGE_OR_CREDENTIAL_BOUNDARY`: Elevated administrator/root privilege or secret keys absent.
7. `PERFORMANCE_OR_DURATION_EXCLUSION`: Long-running stress, soak, or intensive benchmark excluded.
8. `QUARANTINED_DEFECT`: Known tracked issue isolated under active quarantine.

An omitted or skipped test is never a pass. Pull requests and preflight checks must classify every skip against this rubric.
