#!/usr/bin/env python3
"""Fail closed when public presentation surfaces drift from executable truth."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".pytest_cache", ".ruff_cache", ".venv", "build", "dist", "__pycache__"}
TEXT_SUFFIXES = {
    ".cff",
    ".css",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".svg",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

LOCAL_WINDOWS_PATH = re.compile(
    r"(?i)(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]|"
    r"\\\\Users[\\/]|[\\/]\.codex[\\/])"
)
DRIVE_QUALIFIED_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_%])(?:[A-Za-z]:(?:\\\\|[\\/])[A-Za-z0-9._-]{2,})"
)


class DigestTerms:
    """Find hyphen-joined word pairs by the SHA-256 digests of their casefolded text.

    The pairs guarded this way must never appear in public text, so the checker
    keeps only their digests and never spells them itself. A pair matches exactly
    where a case-insensitive, word-bounded pattern for the same pair would. A digest
    keeps a term out of the source; it cannot stop someone who already suspects a
    term from confirming it.
    """

    WORD_RUN = re.compile(r"\w+(?:-\w+)*")

    def __init__(self, *digests: str) -> None:
        self.digests = frozenset(digests)

    def search(self, text: str) -> re.Match[str] | None:
        for run in self.WORD_RUN.finditer(text):
            start = run.start()
            words = run.group(0).split("-")
            for first, second in zip(words, words[1:]):
                pair = text[start : start + len(first) + 1 + len(second)]
                if hashlib.sha256(pair.casefold().encode("utf-8")).hexdigest() in self.digests:
                    return re.compile(re.escape(pair)).match(text, start)
                start += len(first) + 1
        return None


PUBLIC_BOUNDARY_PATTERNS = (
    ("local user or home path", LOCAL_WINDOWS_PATH),
    ("drive-qualified local path", DRIVE_QUALIFIED_PATH),
    ("synthetic private locator", re.compile(r"(?i)evaluator-vault://")),
    ("local model artifact filename", re.compile(r"(?i)\b[a-z0-9_-]+\.gguf\b")),
    ("private deployment field", re.compile(r"(?i)\b(?:model_path|weights_path|lora_path)\b")),
    (
        "private business operations identifier",
        DigestTerms(
            "585785d57be0911dec1a7a4158e21704cd959e7486b6191c470333db777e23a2",
            "842ef1f940f1ae4a818c768a39c7d8e109e0d95484233c61b1ef2540b98e56a2",
        ),
    ),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token shape", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("PyPI token shape", re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key shape", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI-style secret shape", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)

LINEAGE_CAUSALITY_PATTERNS = (
    ("causal lineage", re.compile(r"(?i)\bcausal\s+lineage\b")),
    ("causal ancestors", re.compile(r"(?i)\bcausal\s+ancestors?\b")),
    ("causal process", re.compile(r"(?i)\bcausal\s+process(?:es)?\b")),
    (
        "causal contribution",
        re.compile(r"(?i)\bcausally\s+contribut(?:e|ed|es|ing)\b"),
    ),
)


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.links.append(value)


def _public_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts)
        and path.suffix.lower() in TEXT_SUFFIXES
    )


def _local_target(source: Path, raw: str) -> Path | None:
    value = raw.strip().strip("<>").split(maxsplit=1)[0]
    if not value or value.startswith(("#", "http://", "https://", "mailto:", "data:")):
        return None
    relative = unquote(value.split("#", 1)[0].split("?", 1)[0])
    if not relative:
        return source
    return (source.parent / relative).resolve()


def check_local_links(errors: list[str]) -> None:
    for source in _public_files():
        suffix = source.suffix.lower()
        text = source.read_text(encoding="utf-8")
        links: list[str] = []
        if suffix == ".md":
            links.extend(match.group(1) for match in MARKDOWN_LINK.finditer(text))
        elif suffix == ".html":
            parser = LinkCollector()
            parser.feed(text)
            links.extend(parser.links)
        for raw in links:
            target = _local_target(source, raw)
            if target is not None and not target.exists():
                errors.append(
                    f"broken local link in {source.relative_to(ROOT)}: {raw}"
                )


def check_versions(errors: list[str]) -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = pyproject.split("[project]", 1)
    project_text = "" if len(project_section) != 2 else project_section[1].split("\n[", 1)[0]
    project_match = re.search(r'^version\s*=\s*"([^"]+)"$', project_text, re.MULTILINE)
    if project_match is None:
        errors.append("pyproject.toml has no parseable [project] version")
        return
    expected = project_match.group(1)

    init_text = (ROOT / "src/grounded_hyperset_theory/__init__.py").read_text(encoding="utf-8")
    init_match = re.search(r'^__version__\s*=\s*"([^"]+)"$', init_text, re.MULTILINE)

    citation_path = ROOT / "CITATION.cff"
    citation_match = None
    if citation_path.exists():
        citation_match = re.search(r"^version:\s*([^\s]+)$", citation_path.read_text(encoding="utf-8"), re.MULTILINE)

    zenodo_path = ROOT / ".zenodo.json"
    zenodo_version = None
    if zenodo_path.exists():
        try:
            zenodo_version = json.loads(zenodo_path.read_text(encoding="utf-8")).get("version")
        except Exception:
            zenodo_version = None

    changelog_path = ROOT / "CHANGELOG.md"
    changelog_has_version = False
    if changelog_path.exists():
        changelog_text = changelog_path.read_text(encoding="utf-8")
        changelog_has_version = bool(
            re.search(rf"^## {re.escape(expected)} - \d{{4}}-\d{{2}}-\d{{2}}$", changelog_text, re.MULTILINE)
        )

    found = {
        "src/grounded_hyperset_theory/__init__.py": None if init_match is None else init_match.group(1),
        "CITATION.cff": None if citation_match is None else citation_match.group(1),
        ".zenodo.json": zenodo_version,
    }
    for label, version in found.items():
        if version != expected:
            errors.append(f"version mismatch: pyproject={expected}, {label}={version}")

    if not changelog_has_version:
        errors.append(f"CHANGELOG.md has no dated {expected} release heading")


def public_boundary_violations(text: str) -> list[str]:
    return [label for label, pattern in PUBLIC_BOUNDARY_PATTERNS if pattern.search(text)]


def lineage_causality_violations(text: str) -> list[str]:
    """Reject phrases that silently upgrade recorded ancestry into causality."""
    return [label for label, pattern in LINEAGE_CAUSALITY_PATTERNS if pattern.search(text)]


def check_public_paths(errors: list[str]) -> None:
    checker = Path(__file__).resolve()
    boundary_checker = ROOT / "scripts/check_release_boundary.py"
    exempt_scripts = {checker, boundary_checker}
    for path in _public_files():
        if path.resolve() in exempt_scripts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PUBLIC_BOUNDARY_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{label} leaked into {path.relative_to(ROOT)}:{line}"
                )


def check_lineage_claims(errors: list[str]) -> None:
    checker = Path(__file__).resolve()
    boundary_checker = ROOT / "scripts/check_release_boundary.py"
    exempt_scripts = {checker, boundary_checker}
    for path in _public_files():
        if path.resolve() in exempt_scripts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in LINEAGE_CAUSALITY_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{label} claim in {path.relative_to(ROOT)}:{line}"
                )


def run() -> list[str]:
    errors: list[str] = []
    check_local_links(errors)
    check_versions(errors)
    check_public_paths(errors)
    check_lineage_claims(errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    errors = run()
    if errors:
        for error in errors:
            print(f"[PRESENTATION FAIL] {error}", file=sys.stderr)
        return 1
    print("[PRESENTATION OK] links, versions, and boundary checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
