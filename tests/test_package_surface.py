"""Tests for the packaging claims: ``dependencies = []`` and the export surface.

AGENTS.md names "never introduce third-party runtime dependencies into base
import paths" as a prime directive, and ``pyproject.toml`` declares
``dependencies = []``. Neither was tested. A stray ``import numpy`` at the top of
``math_calculus.py`` would have passed every existing test and every gate,
because the development environment has the package installed -- and would then
fail for the first user who installed this one on its own terms.

The check is therefore made the way a user would experience it: import in a
subprocess started with ``-S``, which disables ``site`` and so removes
site-packages from the path. The README already uses that idiom in its
verification snippet; this turns it into a test.

Version parity is deliberately not retested here. ``scripts/check_presentation.py``
already gates it across pyproject, ``__init__``, CITATION.cff, .zenodo.json and
CHANGELOG.md, and a second copy would drift out of step with the first.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
import subprocess
import sys
from pathlib import Path

import pytest

import grounded_hyperset_theory as package

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

SUBMODULES = sorted(module.name for module in pkgutil.iter_modules(package.__path__))


def _run_isolated(body: str) -> subprocess.CompletedProcess[str]:
    """Run ``body`` in a subprocess with site-packages unavailable."""
    code = f"import sys; sys.path.insert(0, {str(SRC)!r})\n{body}"
    return subprocess.run(
        [sys.executable, "-S", "-c", code], capture_output=True, text=True, cwd=str(ROOT)
    )


def test_site_packages_really_are_unavailable_under_dash_s() -> None:
    """The control for every other isolation test here.

    If ``-S`` did not actually hide third-party packages, the tests below would
    pass vacuously. This uses a package that is installed in the development
    environment and must not be importable under ``-S``.
    """
    proc = _run_isolated("import sympy")
    assert proc.returncode != 0
    assert "No module named 'sympy'" in proc.stderr


def test_the_package_imports_with_no_third_party_packages_available() -> None:
    proc = _run_isolated("import grounded_hyperset_theory as g; print(g.__version__)")
    assert proc.returncode == 0, f"the package needs something it does not declare:\n{proc.stderr}"
    assert proc.stdout.strip() == package.__version__


@pytest.mark.parametrize("name", SUBMODULES)
def test_each_submodule_imports_on_its_own_with_nothing_installed(name: str) -> None:
    """Checked per module, not only through ``__init__``.

    A module that ``__init__`` happens not to reach could otherwise acquire a
    dependency unnoticed.
    """
    proc = _run_isolated(f"import grounded_hyperset_theory.{name}")
    assert proc.returncode == 0, f"{name} needs an undeclared dependency:\n{proc.stderr}"


def test_importing_the_package_loads_no_third_party_module() -> None:
    """``-S`` proves nothing foreign is *required*; this proves nothing foreign
    is *loaded*, which also catches an optional import guarded by ``try``."""
    body = (
        "before = set(sys.modules)\n"
        "import grounded_hyperset_theory\n"
        "std = set(sys.stdlib_module_names)\n"
        "foreign = sorted(\n"
        "    m for m in set(sys.modules) - before\n"
        "    if m.split('.')[0] not in std and not m.startswith('grounded_hyperset_theory')\n"
        ")\n"
        "print(','.join(foreign))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(SRC)!r})\n{body}"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", f"importing the package loaded: {proc.stdout.strip()}"


def test_pyproject_still_declares_no_runtime_dependencies() -> None:
    """The tests above are only meaningful while this is what is promised."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "\ndependencies = []\n" in text


# --------------------------------------------------------------------------
# the export surface
# --------------------------------------------------------------------------


def test_every_exported_name_resolves() -> None:
    missing = [name for name in package.__all__ if not hasattr(package, name)]
    assert missing == []


def test_the_export_list_has_no_duplicates() -> None:
    duplicates = sorted({n for n in package.__all__ if package.__all__.count(n) > 1})
    assert duplicates == []


def test_a_star_import_yields_exactly_the_export_list() -> None:
    namespace: dict[str, object] = {}
    exec("from grounded_hyperset_theory import *", namespace)  # noqa: S102
    starred = sorted(n for n in namespace if not n.startswith("__"))
    assert starred == sorted(package.__all__)


def test_every_name_the_package_imports_is_also_exported() -> None:
    """Closes a gap that this file's own negative control exposed.

    Deleting a name from ``__all__`` broke nothing: ``__init__`` still imports
    it, so ``from grounded_hyperset_theory import ThatName``
    keeps working and every other test here kept passing. But the name silently disappears from ``import *`` and from
    any tool that reads ``__all__``, which is a real regression in the published
    surface.

    The invariant that catches it: every public attribute the package binds at
    module scope is either a submodule, ``annotations`` (leaked into the
    namespace by ``from __future__ import annotations``), or a name in
    ``__all__``.
    """
    import types

    exported = set(package.__all__)
    leaked = sorted(
        name
        for name, value in vars(package).items()
        if not name.startswith("_")
        and name not in exported
        and not isinstance(value, types.ModuleType)
        and name != "annotations"
    )
    assert leaked == []


# --------------------------------------------------------------------------
# the README names things. do they exist, and where?
# --------------------------------------------------------------------------


def _readme_symbols() -> set[str]:
    """Identifiers the README mentions in backticks that look like API names."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    found = set()
    for token in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\(\))?`", text):
        if token[0].isupper() or "_" in token:
            found.add(token)
    return found


def _method_names() -> set[str]:
    """Every public method name on every public class in the package."""
    names: set[str] = set()
    for name in SUBMODULES:
        module = importlib.import_module(f"grounded_hyperset_theory.{name}")
        for value in vars(module).values():
            if inspect.isclass(value) and getattr(value, "__module__", None) == module.__name__:
                names |= {a for a in dir(value) if not a.startswith("_")}
    return names


def _submodule_names() -> set[str]:
    names: set[str] = set()
    for name in SUBMODULES:
        module = importlib.import_module(f"grounded_hyperset_theory.{name}")
        names |= {a for a in vars(module) if not a.startswith("_")}
    return names


def test_the_readme_never_names_something_that_does_not_exist() -> None:
    """The README's feature list names 79 symbols. Every one resolves.

    Six of them are methods rather than module-level functions -- ``is_cauchy``,
    ``is_confluent``, ``is_infinite``, ``is_infinitesimal``, ``cauchy_violation``
    and ``reduction_apg``. Worth knowing, because a check that looked only at
    module scope would report them as missing and be wrong.
    """
    resolvable = set(package.__all__) | _submodule_names() | _method_names()
    unresolved = sorted(_readme_symbols() - resolvable)
    assert unresolved == []


SUBMODULE_ONLY = [
    "APGAutomorphism",
    "Alphabet",
    "CauchySequenceHyperset",
    "DedekindCutHyperset",
    "Grammar",
    "RewritingSystem",
    "SurrealHyperset",
    "Symbol",
    "SyntaxTree",
    "Word",
    "all_orbits",
    "automorphism_group",
    "derivation_step",
    "hyperset_derivative_sequence",
    "hyperset_integer",
    "hyperset_rational",
    "is_symmetric",
    "quote_syntax",
    "quotient_by_symmetry",
    "symmetry_group_order",
    "trajectory_quotient",
    "unquote_syntax",
]


def test_the_readme_symbols_that_need_a_submodule_path_are_exactly_these() -> None:
    """A recorded gap, pinned so it cannot grow quietly.

    Every import example in the README is a top-level one --
    ``from grounded_hyperset_theory import EmptyHyperset, ...`` -- but the
    feature list also names these 22 symbols, and each of them needs its module
    path. ``from grounded_hyperset_theory import automorphism_group`` raises
    ImportError today.

    Nothing here is broken: the names exist and are importable from their
    modules. Widening ``__all__`` would be purely additive and would make the
    README's implied import work, but it also permanently enlarges the public
    surface of a released version, so it is a decision rather than a fix and it
    is not one to take silently.

    This test fails if the list changes in either direction. Shrinking it means
    the decision was taken, and the list should be edited to match.
    """
    top_level = set(package.__all__)
    submodule_only = sorted(
        name for name in _readme_symbols() & _submodule_names() if name not in top_level
    )
    assert submodule_only == SUBMODULE_ONLY


@pytest.mark.parametrize("name", SUBMODULE_ONLY)
def test_each_submodule_only_symbol_really_is_importable_from_its_module(name: str) -> None:
    """The other half: the names are real, so this is discoverability and not
    a broken reference."""
    holders = [
        module
        for module in SUBMODULES
        if hasattr(importlib.import_module(f"grounded_hyperset_theory.{module}"), name)
    ]
    assert holders, f"{name} is named in the README and lives in no module"


def test_the_top_level_import_examples_in_the_readme_all_work() -> None:
    """Every ``from grounded_hyperset_theory import ...`` line in the README,
    executed. A quickstart that does not run is worse than no quickstart."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lines = re.findall(r"^from grounded_hyperset_theory import (.+)$", text, re.MULTILINE)
    assert lines, "no top-level import examples found; this test has gone stale"
    for names in lines:
        for name in (n.strip() for n in names.split(",")):
            assert hasattr(package, name), f"README imports {name}, which is not exported"
