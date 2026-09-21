#!/usr/bin/env python3
"""Assemble documentation into the GitHub Pages artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class PagesBuildError(RuntimeError):
    pass


FAMILY = ROOT / "docs" / "family"


def install_family(output: Path) -> None:
    """Place the family explorer at <site>/family/ however docs were laid out."""
    dest = output / "family"
    if not dest.is_dir():
        if not FAMILY.is_dir():
            raise PagesBuildError(f"family explorer source missing: {FAMILY}")
        shutil.copytree(FAMILY, dest)
    if not (dest / "family-graph.json").is_file():
        raise PagesBuildError("family explorer is missing family-graph.json")


def build(output: Path) -> Path:
    """Build into a new or empty directory and return the site root path."""
    output = output.resolve()
    if output == ROOT:
        raise PagesBuildError("Pages output cannot be the repository root")
    if output.exists() and any(output.iterdir()):
        raise PagesBuildError(f"refusing to merge into non-empty Pages output: {output}")
    if output.exists():
        output.rmdir()

    if not DOCS.is_dir():
        raise PagesBuildError(f"docs directory does not exist: {DOCS}")

    shutil.copytree(DOCS, output)
    install_family(output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        site = build(args.output)
        print(f"[PAGES OK] documentation site assembled at {site}")
        return 0
    except (OSError, PagesBuildError) as exc:
        print(f"[PAGES FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
