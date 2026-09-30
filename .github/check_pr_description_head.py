#!/usr/bin/env python3
"""Refuse a pull-request description that does not name the head it describes.

A description is what a reviewer reads instead of the tree, and it is written for
one commit. It must name that commit on a line of the form

    Current head: <the forty-character commit id>

(`Current signed head:` also serves), and every commit it names that way must be
the head under review. A description that says how many files the head tracks,
as `tracked inventory is N files`, must give the number the head's tree holds.

The tree is read from the platform, never checked out: this runs from the base
branch under `pull_request_target`, holding a token, so nothing from the pull
request is executed or even written to disk. The description is data too; it
reaches this script as a file, never spliced into a command.

This is verifier's `describes-head` distilled to the invariant every repository
shares. verifier's own version also holds the description to its domain ranges
and check totals, which exist in exactly one repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

HEAD_LINE = re.compile(r"Current (?:signed )?head:\s*`?([0-9a-f]{40})`?")
INVENTORY = re.compile(r"tracked inventory is ([\d,]+) files")
# `git ls-files` lists blobs and submodule links; trees are not files.
TRACKED_TYPES = frozenset({"blob", "commit"})


class Unanswered(Exception):
    """A question GitHub did not answer. It is not a no."""


def _gh(arguments: list[str]) -> str:
    try:
        result = subprocess.run(["gh", *arguments], capture_output=True, text=True,
                                encoding="utf-8", timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise Unanswered(f"gh could not be run: {error}") from error
    if result.returncode != 0:
        raise Unanswered(f"gh {' '.join(arguments[:2])} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def tracked_files(repository: str, commit: str) -> int:
    tree = json.loads(_gh(["api", f"repos/{repository}/git/trees/{commit}?recursive=1"]))
    if tree.get("truncated"):
        raise Unanswered(f"GitHub truncated the tree of {commit[:12]}, so its files cannot "
                         "be counted.")
    return sum(1 for entry in tree["tree"] if entry.get("type") in TRACKED_TYPES)


def findings(body: str, head: str, repository: str) -> list[str]:
    found: list[str] = []
    named = HEAD_LINE.findall(body)
    if not named:
        found.append(f"the description names no head. Add a line `Current head: {head}`.")
    for value in named:
        if value != head:
            found.append(f"the description names head {value[:12]}, but the head is "
                         f"{head[:12]}. Describe what the push added, and name the new head.")
    stated = INVENTORY.findall(body)
    if stated:
        actual = tracked_files(repository, head)
        for value in stated:
            if int(value.replace(",", "")) != actual:
                found.append(f"the description states a tracked inventory of {value} files; "
                             f"{head[:12]} tracks {actual}.")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="OWNER/NAME holding the pull request")
    parser.add_argument("--commit", required=True, help="the head the description must name")
    parser.add_argument("--body", required=True, type=Path, help="the description, as a file")
    args = parser.parse_args(argv)

    body = args.body.read_text(encoding="utf-8")
    try:
        found = findings(body, args.commit, args.repo)
    except (Unanswered, KeyError, TypeError, ValueError) as error:
        print(f"[PR DESCRIPTION HEAD] FAIL: {error}")
        return 1
    if found:
        for finding in found:
            print(f"[PR DESCRIPTION HEAD] FAIL: {finding}")
        return 1
    print(f"[PR DESCRIPTION HEAD] PASS: the description names {args.commit[:12]}, the head.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
