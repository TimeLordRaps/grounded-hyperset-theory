"""Build and verify public release artifacts from an exact public Git ref.

The release manifest is an artifact beside the source ZIP, not a tracked file inside
the source tree. That avoids a self-referential commit hash and makes ``source_commit``
both exact and publicly resolvable.
"""

from __future__ import annotations

import argparse
import base64
from configparser import ConfigParser
import csv
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any
import zipfile


SCHEMA_VERSION = "GHT-PUBLIC-RELEASE-1.0"
ARCHIVE_STEM = "grounded-hyperset-theory"
DISTRIBUTION_NAME = "grounded-hyperset-theory"
IMPORT_PACKAGE = "grounded_hyperset_theory"
CONSOLE_SCRIPTS: dict[str, str] = {}

_GENERATED_WHEEL_TEXT_NAMES = {
    "METADATA",
    "WHEEL",
    "entry_points.txt",
    "top_level.txt",
}


class ReleaseError(RuntimeError):
    """Release construction or verification failed closed."""


def _run(repo: Path, *args: str, env: dict[str, str] | None = None) -> bytes:
    completed = subprocess.run(
        list(args), cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseError(f"command failed ({' '.join(args)}): {detail}")
    return completed.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"byte_size": len(data), "sha256": _sha256(data)}


def _resolved_commit(repo: Path, ref: str) -> str:
    return _run(repo, "git", "rev-parse", f"{ref}^{{commit}}").decode().strip()


def _canonical_repository_url(value: str) -> str:
    """Return one stable public coordinate for common Git remote spellings."""
    candidate = value.strip().rstrip("/")
    scp_match = re.fullmatch(r"git@([^:]+):(.+)", candidate)
    ssh_match = re.fullmatch(r"ssh://git@([^/]+)/(.+)", candidate)
    if scp_match:
        candidate = f"https://{scp_match.group(1)}/{scp_match.group(2)}"
    elif ssh_match:
        candidate = f"https://{ssh_match.group(1)}/{ssh_match.group(2)}"
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    if not candidate:
        raise ReleaseError("origin repository URL is empty")
    return candidate


def _repository_url(repo: Path) -> str:
    try:
        raw = _run(repo, "git", "remote", "get-url", "origin").decode()
        return _canonical_repository_url(raw)
    except ReleaseError:
        return "https://github.com/TimeLordRaps/grounded-hyperset-theory"


def _zip_timestamp(epoch: str) -> tuple[int, int, int, int, int, int]:
    timestamp = datetime.fromtimestamp(int(epoch), timezone.utc)
    if timestamp.year < 1980 or timestamp.year > 2107:
        raise ReleaseError(f"commit timestamp is outside the ZIP range: {epoch}")
    return (
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second - (timestamp.second % 2),
    )


def _canonical_zip_info(name: str, epoch: str, *, is_dir: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_zip_timestamp(epoch))
    info.create_system = 3
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.compress_type = zipfile.ZIP_STORED
    info.comment = b""
    info.extra = b""
    info.internal_attr = 0
    mode = (stat.S_IFDIR | 0o755) if is_dir else (stat.S_IFREG | 0o644)
    info.external_attr = mode << 16
    if is_dir:
        info.external_attr |= 0x10
    return info


def _write_canonical_zip(
    destination: Path,
    members: dict[str, tuple[bytes, bool]],
    epoch: str,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as bundle:
        for name in sorted(members):
            data, is_dir = members[name]
            if (
                not name
                or name.startswith("/")
                or "\\" in name
                or ".." in Path(name).parts
            ):
                raise ReleaseError(f"unsafe ZIP member name: {name}")
            if is_dir and not name.endswith("/"):
                raise ReleaseError(f"ZIP directory lacks trailing slash: {name}")
            info = _canonical_zip_info(name, epoch, is_dir=is_dir)
            bundle.writestr(info, b"" if is_dir else data)


def _normalize_source_archive(source: Path, destination: Path, epoch: str) -> None:
    """Rewrite git archive output without host timezone or ZIP metadata."""
    with zipfile.ZipFile(source) as bundle:
        members: dict[str, tuple[bytes, bool]] = {}
        for info in bundle.infolist():
            if info.filename in members:
                raise ReleaseError(f"duplicate source ZIP member: {info.filename}")
            members[info.filename] = (bundle.read(info), info.is_dir())
    _write_canonical_zip(destination, members, epoch)


def _normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _record_digest(data: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + encoded.decode("ascii")


def _normalize_wheel(source: Path, destination: Path, epoch: str) -> None:
    """Canonicalize generated metadata, RECORD, member order, modes, and timestamps."""
    with zipfile.ZipFile(source) as bundle:
        infos = bundle.infolist()
        record_paths = [
            info.filename for info in infos if info.filename.endswith(".dist-info/RECORD")
        ]
        signature_paths = [
            info.filename
            for info in infos
            if info.filename.endswith((".dist-info/RECORD.jws", ".dist-info/RECORD.p7s"))
        ]
        if len(record_paths) != 1:
            raise ReleaseError(f"wheel must contain exactly one RECORD: {source}")
        if signature_paths:
            raise ReleaseError("normalization does not accept pre-signed wheel RECORD files")
        record_path = record_paths[0]
        members: dict[str, tuple[bytes, bool]] = {}
        for info in infos:
            if info.filename == record_path:
                continue
            if info.filename in members:
                raise ReleaseError(f"duplicate wheel member: {info.filename}")
            data = bundle.read(info)
            leaf = info.filename.rsplit("/", 1)[-1]
            if ".dist-info/" in info.filename and leaf in _GENERATED_WHEEL_TEXT_NAMES:
                data = _normalize_newlines(data)
            members[info.filename] = (data, info.is_dir())

    rows = io.StringIO(newline="")
    writer = csv.writer(rows, lineterminator="\n")
    for name in sorted(members):
        data, is_dir = members[name]
        if not is_dir:
            writer.writerow((name, _record_digest(data), str(len(data))))
    writer.writerow((record_path, "", ""))
    members[record_path] = (rows.getvalue().encode("utf-8"), False)
    _write_canonical_zip(destination, members, epoch)


def _archive_inventory(archive: Path, prefix: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise ReleaseError(f"archive member escapes declared prefix: {info.filename}")
            relative = info.filename[len(prefix) :]
            if not relative:
                raise ReleaseError("archive contains an empty relative path")
            if relative in result:
                raise ReleaseError(f"archive contains duplicate member: {relative}")
            data = bundle.read(info)
            result[relative] = {"byte_size": len(data), "sha256": _sha256(data)}
    return dict(sorted(result.items()))


def _canonical_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _metadata_identity(payload: bytes, *, artifact: str) -> tuple[str, str]:
    metadata = BytesParser(policy=policy.default).parsebytes(payload)
    name = str(metadata.get("Name", ""))
    version = str(metadata.get("Version", ""))
    if not name or not version:
        raise ReleaseError(f"distribution metadata lacks Name or Version: {artifact}")
    return name, version


def _normalize_sdist(source: Path, destination: Path, epoch: str) -> None:
    """Rewrite an sdist with stable generated text, gzip, and tar metadata."""
    timestamp = int(epoch)
    with tarfile.open(source, "r:gz") as bundle:
        members = sorted(bundle.getmembers(), key=lambda item: item.name)
        roots = {member.name.split("/", 1)[0] for member in members if member.name}
        if len(roots) != 1:
            raise ReleaseError(f"sdist must contain exactly one root directory: {source}")

        materialized: list[tuple[tarfile.TarInfo, bytes | None]] = []
        for member in members:
            if member.isdir():
                data = None
            elif member.isfile():
                extracted = bundle.extractfile(member)
                if extracted is None:
                    raise ReleaseError(f"sdist member is unreadable: {member.name}")
                data = extracted.read()
                relative = member.name.split("/", 1)[1] if "/" in member.name else ""
                generated = (
                    relative in {"PKG-INFO", "setup.cfg"}
                    or ".egg-info/" in relative
                )
                if generated:
                    data = _normalize_newlines(data)
            else:
                raise ReleaseError(
                    f"sdist contains unsupported non-file member: {member.name}"
                )
            materialized.append((member, data))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, compresslevel=0, mtime=timestamp
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT
            ) as normalized:
                for original, data in materialized:
                    member = tarfile.TarInfo(original.name.replace("\\", "/"))
                    member.mtime = timestamp
                    member.uid = 0
                    member.gid = 0
                    member.uname = ""
                    member.gname = ""
                    if data is None:
                        member.type = tarfile.DIRTYPE
                        member.mode = 0o755
                        member.size = 0
                        normalized.addfile(member)
                    else:
                        member.type = tarfile.REGTYPE
                        member.mode = 0o644
                        member.size = len(data)
                        normalized.addfile(member, io.BytesIO(data))


def _verify_python_distributions(wheel: Path, sdist: Path, release: str) -> None:
    expected_name = _canonical_distribution_name(DISTRIBUTION_NAME)

    with zipfile.ZipFile(wheel) as bundle:
        names = bundle.namelist()
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        entry_paths = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        if len(metadata_paths) != 1:
            raise ReleaseError("wheel must contain exactly one METADATA")
        name, version = _metadata_identity(
            bundle.read(metadata_paths[0]), artifact=wheel.name
        )
        if CONSOLE_SCRIPTS:
            if len(entry_paths) != 1:
                raise ReleaseError("wheel must contain one entry_points.txt")
            parser = ConfigParser(interpolation=None)
            parser.read_string(bundle.read(entry_paths[0]).decode("utf-8"))
            scripts = (
                dict(parser["console_scripts"])
                if parser.has_section("console_scripts")
                else {}
            )
            if scripts != CONSOLE_SCRIPTS:
                raise ReleaseError(f"wheel console scripts differ from the expected set: {scripts}")
        else:
            if entry_paths:
                parser = ConfigParser(interpolation=None)
                parser.read_string(bundle.read(entry_paths[0]).decode("utf-8"))
                scripts = (
                    dict(parser["console_scripts"])
                    if parser.has_section("console_scripts")
                    else {}
                )
                if scripts:
                    raise ReleaseError(f"unexpected console scripts found: {scripts}")

        if f"{IMPORT_PACKAGE}/__init__.py" not in names:
            raise ReleaseError(f"wheel lacks import package {IMPORT_PACKAGE}")

    if _canonical_distribution_name(name) != expected_name or version != release:
        raise ReleaseError(
            f"wheel identity mismatch: expected {DISTRIBUTION_NAME} {release}, "
            f"found {name} {version}"
        )

    with tarfile.open(sdist, "r:gz") as bundle:
        members = bundle.getmembers()
        names = [member.name for member in members]
        roots = {path.split("/", 1)[0] for path in names if path}
        if len(roots) != 1:
            raise ReleaseError("sdist must contain exactly one root directory")
        root = next(iter(roots))
        metadata_members = [
            member for member in members if member.name == f"{root}/PKG-INFO"
        ]
        if len(metadata_members) != 1:
            raise ReleaseError("sdist must contain one root PKG-INFO")
        metadata_file = bundle.extractfile(metadata_members[0])
        if metadata_file is None:
            raise ReleaseError("sdist PKG-INFO is unreadable")
        sdist_name, sdist_version = _metadata_identity(
            metadata_file.read(), artifact=sdist.name
        )
        if f"{root}/src/{IMPORT_PACKAGE}/__init__.py" not in names:
            raise ReleaseError(f"sdist lacks import package {IMPORT_PACKAGE}")

    if (
        _canonical_distribution_name(sdist_name) != expected_name
        or sdist_version != release
    ):
        raise ReleaseError(
            f"sdist identity mismatch: expected {DISTRIBUTION_NAME} {release}, "
            f"found {sdist_name} {sdist_version}"
        )


def build_source(repo: Path, ref: str, release: str, output_dir: Path) -> tuple[Path, Path]:
    repo = repo.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    commit = _resolved_commit(repo, ref)
    prefix = f"{ARCHIVE_STEM}-{release}/"
    archive = output_dir / f"{ARCHIVE_STEM}-{release}.zip"
    manifest_path = output_dir / f"{ARCHIVE_STEM}-{release}.manifest.json"
    epoch = _run(repo, "git", "show", "-s", "--format=%ct", commit).decode().strip()

    with tempfile.TemporaryDirectory(prefix="ght-source-archive-") as temporary:
        raw_archive = Path(temporary) / "raw.zip"
        _run(
            repo,
            "git",
            "archive",
            "--format=zip",
            f"--prefix={prefix}",
            f"--output={raw_archive}",
            commit,
        )
        _normalize_source_archive(raw_archive, archive, epoch)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "release": release,
        "scope": (
            "public Grounded Hyperset Theory reference implementation, "
            "formal calculi pathways, examples, tests, and public project process"
        ),
        "source": {
            "repository": _repository_url(repo),
            "ref": ref,
            "commit": commit,
            "archive_prefix": prefix,
            "byte_semantics": (
                "exact Git blob member bytes in a platform-independent canonical ZIP"
            ),
        },
        "distribution": {
            "name": DISTRIBUTION_NAME,
            "import_package": IMPORT_PACKAGE,
            "console_scripts": dict(sorted(CONSOLE_SCRIPTS.items())),
        },
        "artifacts": {
            archive.name: _file_record(archive),
        },
        "files": _archive_inventory(archive, prefix),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return archive, manifest_path


def _build_wheel_once(source_archive: Path, prefix: str, destination: Path, epoch: str) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ght-wheel-") as temporary:
        temporary_path = Path(temporary)
        with zipfile.ZipFile(source_archive) as bundle:
            bundle.extractall(temporary_path)
        source = temporary_path / prefix.rstrip("/")
        raw_output = temporary_path / "raw"
        env = dict(os.environ)
        env["SOURCE_DATE_EPOCH"] = epoch
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-deps",
                "--wheel-dir",
                str(raw_output),
                str(source),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode:
            raise ReleaseError(
                "wheel build failed: "
                + completed.stderr.decode("utf-8", errors="replace").strip()
            )
        wheels = sorted(raw_output.glob("*.whl"))
        if len(wheels) != 1:
            raise ReleaseError(f"expected one raw wheel, found {len(wheels)} in {raw_output}")
        normalized = destination / wheels[0].name
        _normalize_wheel(wheels[0], normalized, epoch)
    return normalized


def _build_sdist_once(
    source_archive: Path,
    prefix: str,
    destination: Path,
    epoch: str,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ght-sdist-") as temporary:
        temporary_path = Path(temporary)
        with zipfile.ZipFile(source_archive) as bundle:
            bundle.extractall(temporary_path / "source")
        source = temporary_path / "source" / prefix.rstrip("/")
        raw_output = temporary_path / "raw"
        env = dict(os.environ)
        env["SOURCE_DATE_EPOCH"] = epoch
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                "--outdir",
                str(raw_output),
                str(source),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode:
            raise ReleaseError(
                "sdist build failed: "
                + completed.stderr.decode("utf-8", errors="replace").strip()
            )
        sdists = sorted(raw_output.glob("*.tar.gz"))
        if len(sdists) != 1:
            raise ReleaseError(
                f"expected one raw sdist, found {len(sdists)} in {raw_output}"
            )
        normalized = destination / sdists[0].name
        _normalize_sdist(sdists[0], normalized, epoch)
    return normalized


def build_all(
    repo: Path, ref: str, release: str, output_dir: Path
) -> tuple[Path, Path, Path, Path]:
    archive, manifest_path = build_source(repo, ref, release, output_dir)
    commit = _resolved_commit(repo.resolve(), ref)
    epoch = _run(repo.resolve(), "git", "show", "-s", "--format=%ct", commit).decode().strip()
    prefix = f"{ARCHIVE_STEM}-{release}/"

    with tempfile.TemporaryDirectory(prefix="ght-wheel-builds-") as temporary:
        temporary_path = Path(temporary)
        first = _build_wheel_once(archive, prefix, temporary_path / "first", epoch)
        second = _build_wheel_once(archive, prefix, temporary_path / "second", epoch)
        if first.name != second.name or first.read_bytes() != second.read_bytes():
            raise ReleaseError("two clean wheel builds were not byte-identical")
        wheel = output_dir / first.name
        shutil.copy2(first, wheel)

    with tempfile.TemporaryDirectory(prefix="ght-sdist-builds-") as temporary:
        temporary_path = Path(temporary)
        first = _build_sdist_once(archive, prefix, temporary_path / "first", epoch)
        second = _build_sdist_once(archive, prefix, temporary_path / "second", epoch)
        if first.name != second.name or first.read_bytes() != second.read_bytes():
            raise ReleaseError("two normalized clean sdist builds were not byte-identical")
        sdist = output_dir / first.name
        shutil.copy2(first, sdist)

    _verify_python_distributions(wheel, sdist, release)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][wheel.name] = _file_record(wheel)
    manifest["artifacts"][sdist.name] = _file_record(sdist)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    verify_manifest(repo, manifest_path, output_dir)
    return archive, wheel, sdist, manifest_path


def compare_artifact_directories(first: Path, second: Path) -> int:
    """Fail unless two build directories contain the same byte-identical files."""
    first = first.resolve()
    second = second.resolve()
    first_files = {
        path.relative_to(first).as_posix(): path
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path
        for path in second.rglob("*")
        if path.is_file()
    }
    if set(first_files) != set(second_files):
        missing_first = sorted(set(second_files) - set(first_files))
        missing_second = sorted(set(first_files) - set(second_files))
        raise ReleaseError(
            "artifact file sets differ: "
            f"missing from first={missing_first}, missing from second={missing_second}"
        )
    if not first_files:
        raise ReleaseError("artifact directories are empty")
    for name in sorted(first_files):
        first_record = _file_record(first_files[name])
        second_record = _file_record(second_files[name])
        if first_record != second_record:
            raise ReleaseError(
                f"artifact bytes differ for {name}: {first_record} != {second_record}"
            )
    return len(first_files)


def verify_manifest(repo: Path, manifest_path: Path, artifact_dir: Path | None = None) -> None:
    repo = repo.resolve()
    manifest_path = manifest_path.resolve()
    artifact_dir = artifact_dir.resolve() if artifact_dir else manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseError(f"unsupported release manifest schema: {manifest.get('schema_version')}")

    source = manifest.get("source", {})
    ref = str(source.get("ref", ""))
    commit = str(source.get("commit", ""))
    if not ref or not commit:
        raise ReleaseError("manifest source ref and commit are required")
    resolved = _resolved_commit(repo, ref)
    if resolved != commit:
        raise ReleaseError(f"source ref resolves to {resolved}, manifest binds {commit}")

    artifacts = manifest.get("artifacts", {})
    for filename, expected in artifacts.items():
        path = artifact_dir / filename
        if not path.is_file() or _file_record(path) != expected:
            raise ReleaseError(f"artifact digest or byte size mismatch: {filename}")

    distribution = manifest.get("distribution")
    if distribution is not None:
        expected_distribution = {
            "name": DISTRIBUTION_NAME,
            "import_package": IMPORT_PACKAGE,
            "console_scripts": dict(sorted(CONSOLE_SCRIPTS.items())),
        }
        if distribution != expected_distribution:
            raise ReleaseError("release manifest distribution identity is not canonical")
        wheels = [artifact_dir / name for name in artifacts if name.endswith(".whl")]
        sdists = [artifact_dir / name for name in artifacts if name.endswith(".tar.gz")]
        if wheels or sdists:
            if len(wheels) != 1 or len(sdists) != 1:
                raise ReleaseError(
                    "a Python distribution release must bind one wheel and one sdist"
                )
            _verify_python_distributions(wheels[0], sdists[0], str(manifest["release"]))

    declared_prefix = str(source.get("archive_prefix", "")).rstrip("/")
    archive_name = (
        f"{declared_prefix}.zip"
        if declared_prefix
        else f"{ARCHIVE_STEM}-{manifest['release']}.zip"
    )
    archive = artifact_dir / archive_name
    if archive_name not in artifacts or not archive.is_file():
        raise ReleaseError(f"source archive is not bound: {archive_name}")
    prefix = str(source.get("archive_prefix", ""))
    inventory = _archive_inventory(archive, prefix)
    if inventory != manifest.get("files"):
        raise ReleaseError("source archive member inventory does not match the manifest")

    tracked = _run(repo, "git", "ls-tree", "-r", "--name-only", commit).decode().splitlines()
    if sorted(tracked) != sorted(inventory):
        raise ReleaseError("source archive file set does not match the bound Git commit")
    with zipfile.ZipFile(archive) as bundle:
        for relative, expected in inventory.items():
            archive_bytes = bundle.read(prefix + relative)
            git_bytes = _run(repo, "git", "show", f"{commit}:{relative}")
            if archive_bytes != git_bytes or _sha256(git_bytes) != expected["sha256"]:
                raise ReleaseError(f"archive bytes do not match Git blob: {relative}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("source", "build"):
        command = commands.add_parser(name)
        command.add_argument("--ref", required=True)
        command.add_argument("--release", required=True)
        command.add_argument("--output-dir", required=True, type=Path)

    verify = commands.add_parser("verify")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--artifact-dir", type=Path)

    compare = commands.add_parser("compare")
    compare.add_argument("first", type=Path)
    compare.add_argument("second", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "source":
            archive, manifest = build_source(args.repo, args.ref, args.release, args.output_dir)
            verify_manifest(args.repo, manifest, args.output_dir)
            print(f"[PASS] source archive: {archive}")
            print(f"[PASS] release manifest: {manifest}")
        elif args.command == "build":
            archive, wheel, sdist, manifest = build_all(
                args.repo, args.ref, args.release, args.output_dir
            )
            print(f"[PASS] source archive: {archive}")
            print(f"[PASS] reproducible wheel: {wheel}")
            print(f"[PASS] reproducible sdist: {sdist}")
            print(f"[PASS] release manifest: {manifest}")
        elif args.command == "verify":
            verify_manifest(args.repo, args.manifest, args.artifact_dir)
            print(f"[PASS] release manifest verified: {args.manifest}")
        else:
            count = compare_artifact_directories(args.first, args.second)
            print(f"[PASS] {count} release artifacts are byte-identical")
    except (OSError, ReleaseError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
