"""Check imports and representative calls from a clean, non-editable wheel install."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def run(command: list[str], *, cwd: Path, timeout: int = 180) -> None:
    print(
        f"START installed-wheel check: {Path(command[0]).name} {' '.join(command[1:3])}",
        flush=True,
    )
    subprocess.run(command, cwd=cwd, check=True, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    wheels = sorted(args.wheel_dir.resolve().glob("*.whl"))
    if not wheels:
        raise SystemExit(f"No wheels found in {args.wheel_dir}")
    target_wheels = [w for w in wheels if "grounded_hyperset_theory" in w.name]
    wheel = str(target_wheels[0] if target_wheels else wheels[0])

    with tempfile.TemporaryDirectory(prefix="installed-wheel-ght-") as temporary:
        root = Path(temporary)
        environment = root / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

        run([str(python), "-m", "pip", "install", "--no-deps", wheel], cwd=root)
        run([str(python), "-m", "pip", "check"], cwd=root)

        probe = (
            "import importlib, pathlib, sys; "
            "module = importlib.import_module('grounded_hyperset_theory'); "
            "assert pathlib.Path(module.__file__).resolve().is_relative_to("
            "pathlib.Path(sys.prefix).resolve()), 'import did not come from the isolated environment'; "
            "omega = module.QuineAtom(); "
            "assert omega in omega, 'Quine atom self-membership failed'; "
            "assert module.EmptyHyperset().is_empty; "
            "ord3 = module.von_neumann_ordinal(3); "
            "assert ord3.cardinality() == 3; "
            "assert ord3.is_ordinal(); "
            "assert int(ord3) == 3; "
            "assert module.ordinal_add(ord3, module.von_neumann_ordinal(2)) == module.von_neumann_ordinal(5); "
            "assert hash(omega) == hash(omega); "
            "assert len(module.EmptyHyperset().powerset()) == 1; "
            "p = module.pair(module.EmptyHyperset(), omega); "
            "assert len(p) == 2; "
            "apg = module.AccessiblePointedGraph(root=0, edges={0: [1, 2], 1: [2], 2: []}); "
            "assert not apg.has_cycles(); "
            "perm = module.Permutation.from_mapping({'x': 'y', 'y': 'x'}); "
            "assert perm.order() == 2; "
            "liar = module.liar_sentence(); "
            "assert not liar.is_empty; "
            "cut = module.DedekindCut.sqrt_two(); "
            "low, high = cut.binary_search_interval(module.GroundedRational(1), module.GroundedRational(2), iterations=10); "
            "assert float(low) < 1.415 and float(high) > 1.414; "
            "print('PASS: installed grounded_hyperset_theory wheel is importable and verified across all pathways')"
        )
        run([str(python), "-I", "-c", probe], cwd=root, timeout=30)


if __name__ == "__main__":
    main()
