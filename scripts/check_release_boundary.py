#!/usr/bin/env python3
"""Fail closed when a release archive contains private or secret-shaped text."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import zipfile

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
METADATA_NAMES = {"METADATA", "PKG-INFO", "entry_points.txt", "top_level.txt"}

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


def _should_scan(name: str) -> bool:
    path = PurePosixPath(name)
    if path.as_posix().endswith("/scripts/check_release_boundary.py") or path.as_posix().endswith("/scripts/check_presentation.py"):
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in METADATA_NAMES


def _scan_text(artifact: Path, member: str, payload: bytes, errors: list[str]) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"non-UTF-8 text member: {artifact.name}:{member}")
        return
    subject = f"{member}\n{text}"
    for label, pattern in PUBLIC_BOUNDARY_PATTERNS:
        match = pattern.search(subject)
        if match:
            errors.append(
                f"{label} in {artifact.name}:{member}: {match.group(0)!r}"
            )


def _scan_zip(path: Path, errors: list[str]) -> int:
    count = 0
    with zipfile.ZipFile(path) as bundle:
        for info in bundle.infolist():
            if info.is_dir() or not _should_scan(info.filename):
                continue
            _scan_text(path, info.filename, bundle.read(info), errors)
            count += 1
    return count


def _scan_tar(path: Path, errors: list[str]) -> int:
    count = 0
    with tarfile.open(path, "r:gz") as bundle:
        for member in bundle.getmembers():
            if not member.isfile() or not _should_scan(member.name):
                continue
            extracted = bundle.extractfile(member)
            if extracted is None:
                errors.append(f"unreadable text member: {path.name}:{member.name}")
                continue
            _scan_text(path, member.name, extracted.read(), errors)
            count += 1
    return count


def check_artifact(path: Path, errors: list[str]) -> int:
    if path.name.endswith((".zip", ".whl")):
        return _scan_zip(path, errors)
    if path.name.endswith(".tar.gz"):
        return _scan_tar(path, errors)
    raise ValueError(f"unsupported release artifact: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args(argv)

    errors: list[str] = []
    scanned = 0
    expanded_artifacts: list[Path] = []
    for raw in args.artifacts:
        raw_str = str(raw)
        if any(c in raw_str for c in "*?[]"):
            p = Path(raw_str)
            parent = p.parent if str(p.parent) != "" else Path(".")
            matches = sorted(parent.glob(p.name))
            if not matches:
                errors.append(f"pattern matched no release artifacts: {raw_str}")
            expanded_artifacts.extend(matches)
        else:
            expanded_artifacts.append(raw)

    for artifact in expanded_artifacts:
        if not artifact.is_file():
            errors.append(f"release artifact does not exist: {artifact}")
            continue
        try:
            scanned += check_artifact(artifact, errors)
        except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
            errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"[BOUNDARY FAIL] {error}", file=sys.stderr)
        return 1
    print(f"[BOUNDARY OK] scanned {scanned} text members in {len(expanded_artifacts)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
