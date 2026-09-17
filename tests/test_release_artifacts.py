"""Tests for reproducible release artifact building, verification, and comparison."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_artifacts.py"

SPEC = importlib.util.spec_from_file_location("ght_release_artifacts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release_artifacts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_artifacts)


def _init_test_git_repo(path: Path) -> Path:
    """Initialize a reproducible minimal git repo with a commit for testing."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "ci-test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True, capture_output=True)

    (path / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    pyproject = (
        '[build-system]\n'
        'requires = ["hatchling>=1.27"]\n'
        'build-backend = "hatchling.build"\n\n'
        '[project]\n'
        'name = "grounded-hyperset-theory"\n'
        'version = "0.2.0"\n'
        'description = "Test package"\n'
        'dependencies = []\n'
    )
    (path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    src_dir = path / "src" / "grounded_hyperset_theory"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "0.2.0"\n', encoding="utf-8")
    (path / "README.md").write_text("# Grounded Hyperset Theory\n", encoding="utf-8")
    (path / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial test commit", "--date", "2026-09-17T12:00:00Z"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    return path


def test_build_source_and_verify_manifest(tmp_path: Path) -> None:
    repo = _init_test_git_repo(tmp_path / "repo")
    out_dir = tmp_path / "dist"

    archive, manifest_path = release_artifacts.build_source(repo, "HEAD", "0.2.0", out_dir)
    assert archive.is_file()
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "GHT-PUBLIC-RELEASE-1.0"
    assert manifest["release"] == "0.2.0"
    assert manifest["distribution"]["name"] == "grounded-hyperset-theory"
    assert manifest["distribution"]["import_package"] == "grounded_hyperset_theory"
    assert "src/grounded_hyperset_theory/__init__.py" in manifest["files"]
    assert "pyproject.toml" in manifest["files"]

    # Manifest verification passes on untampered build
    release_artifacts.verify_manifest(repo, manifest_path, out_dir)


def test_verify_manifest_fails_on_archive_tampering(tmp_path: Path) -> None:
    repo = _init_test_git_repo(tmp_path / "repo")
    out_dir = tmp_path / "dist"

    archive, manifest_path = release_artifacts.build_source(repo, "HEAD", "0.2.0", out_dir)

    # Tamper with archive by appending a byte
    with archive.open("ab") as f:
        f.write(b"\x00")

    with pytest.raises(release_artifacts.ReleaseError, match="artifact digest or byte size mismatch"):
        release_artifacts.verify_manifest(repo, manifest_path, out_dir)


def test_compare_artifact_directories(tmp_path: Path) -> None:
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "file.txt").write_bytes(b"hello world")
    (dir2 / "file.txt").write_bytes(b"hello world")

    # Identical directories pass
    count = release_artifacts.compare_artifact_directories(dir1, dir2)
    assert count == 1

    # Differing content fails
    (dir2 / "file.txt").write_bytes(b"hello tampered")
    with pytest.raises(release_artifacts.ReleaseError, match="artifact bytes differ"):
        release_artifacts.compare_artifact_directories(dir1, dir2)

    # Missing file fails
    (dir2 / "file.txt").unlink()
    with pytest.raises(release_artifacts.ReleaseError, match="artifact file sets differ"):
        release_artifacts.compare_artifact_directories(dir1, dir2)


def test_cli_source_and_verify(tmp_path: Path) -> None:
    repo = _init_test_git_repo(tmp_path / "repo")
    out_dir = tmp_path / "cli_dist"

    cmd_source = [
        sys.executable,
        str(SCRIPT),
        "--repo",
        str(repo),
        "source",
        "--ref",
        "HEAD",
        "--release",
        "0.2.0",
        "--output-dir",
        str(out_dir),
    ]
    res_source = subprocess.run(cmd_source, capture_output=True, text=True)
    assert res_source.returncode == 0, res_source.stderr
    assert "[PASS] source archive:" in res_source.stdout

    manifest = out_dir / "grounded-hyperset-theory-0.2.0.manifest.json"
    cmd_verify = [
        sys.executable,
        str(SCRIPT),
        "--repo",
        str(repo),
        "verify",
        str(manifest),
    ]
    res_verify = subprocess.run(cmd_verify, capture_output=True, text=True)
    assert res_verify.returncode == 0, res_verify.stderr
    assert "[PASS] release manifest verified:" in res_verify.stdout


def test_build_all_produces_reproducible_distribution_artifacts(tmp_path: Path) -> None:
    repo = _init_test_git_repo(tmp_path / "repo")
    out_dir_1 = tmp_path / "dist1"
    out_dir_2 = tmp_path / "dist2"

    archive1, wheel1, sdist1, manifest1 = release_artifacts.build_all(repo, "HEAD", "0.2.0", out_dir_1)
    assert archive1.is_file()
    assert wheel1.is_file()
    assert sdist1.is_file()
    assert manifest1.is_file()

    manifest_data = json.loads(manifest1.read_text(encoding="utf-8"))
    assert wheel1.name in manifest_data["artifacts"]
    assert sdist1.name in manifest_data["artifacts"]
    assert archive1.name in manifest_data["artifacts"]

    release_artifacts.verify_manifest(repo, manifest1, out_dir_1)

    # Build second time into out_dir_2 and assert byte-identity
    archive2, wheel2, sdist2, manifest2 = release_artifacts.build_all(repo, "HEAD", "0.2.0", out_dir_2)
    assert archive1.read_bytes() == archive2.read_bytes()
    assert wheel1.read_bytes() == wheel2.read_bytes()
    assert sdist1.read_bytes() == sdist2.read_bytes()
    assert manifest1.read_bytes() == manifest2.read_bytes()
    assert release_artifacts.compare_artifact_directories(out_dir_1, out_dir_2) == 4
