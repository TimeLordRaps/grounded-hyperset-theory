"""The public first impression is a checked repository surface."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_professional_presentation_surface_has_no_drift() -> None:
    path = ROOT / "scripts/check_presentation.py"
    spec = importlib.util.spec_from_file_location("check_presentation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.run() == []


def test_public_boundary_catches_private_coordinates_without_naming_them() -> None:
    path = ROOT / "scripts/check_presentation.py"
    spec = importlib.util.spec_from_file_location("check_presentation_boundaries", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    drive_path = "E:" + "\\" + "private-workspace" + "\\" + "plan.md"
    private_locator = "evaluator" + "-vault://artifact"
    local_artifact = "private-model" + ".gguf"
    deployment_field = "model" + "_path"
    email_leak = "dev" + "@" + "example.com"
    assert "drive-qualified local path" in module.public_boundary_violations(drive_path)
    assert "synthetic private locator" in module.public_boundary_violations(private_locator)
    assert "local model artifact filename" in module.public_boundary_violations(local_artifact)
    assert "private deployment field" in module.public_boundary_violations(deployment_field)
    assert "email address" in module.public_boundary_violations(email_leak)


@pytest.mark.parametrize("script", ["check_presentation.py", "check_release_boundary.py"])
def test_private_identifiers_are_matched_by_digest_and_never_spelled(script: str) -> None:
    path = ROOT / "scripts" / script
    spec = importlib.util.spec_from_file_location(f"{path.stem}_digests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    guard = dict(module.PUBLIC_BOUNDARY_PATTERNS)["private business operations identifier"]
    assert isinstance(guard, module.DigestTerms)
    assert guard.digests == {
        "585785d57be0911dec1a7a4158e21704cd959e7486b6191c470333db777e23a2",
        "842ef1f940f1ae4a818c768a39c7d8e109e0d95484233c61b1ef2540b98e56a2",
    }

    # The guarded pairs are never spelled, here or in the checker, so parity with the
    # word-bounded, case-insensitive pattern the digests replace is shown on a stand-in.
    stand_in = module.DigestTerms(hashlib.sha256(b"sample-term").hexdigest())
    spelled = re.compile(r"(?i)\b(?:sample-term)\b")
    for text in (
        "sample-term",
        "Sample-Term.",
        "see (SAMPLE-TERM), then",
        "pre-sample-term-post",
        "sample-sample-term",
        "sample-term-sample-term",
        "xsample-term",
        "sample-termx",
        "sample_term",
        "sample--term",
        "sample term",
        "sampleterm",
        "ésample-term",
        "",
    ):
        found, expected = stand_in.search(text), spelled.search(text)
        assert (found is None) == (expected is None), text
        if found is not None and expected is not None:
            assert (found.span(), found.group(0)) == (expected.span(), expected.group(0)), text


def test_lineage_claim_gate_rejects_causal_upgrades_without_blocking_boundaries() -> None:
    path = ROOT / "scripts/check_presentation.py"
    spec = importlib.util.spec_from_file_location("check_presentation_lineage", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    causal_lineage = "causal" + " lineage"
    causal_ancestors = "causal" + " ancestors"
    causal_process = "causal" + " process"
    causal_contribution = "causally" + " contributed"
    for phrase in (
        causal_lineage,
        causal_ancestors,
        causal_process,
        causal_contribution,
    ):
        assert module.lineage_causality_violations(phrase)

    assert module.lineage_causality_violations("recorded lineage") == []
    assert module.lineage_causality_violations(
        "The recorded edge does not establish causal influence."
    ) == []


def test_pages_artifact_assembles_documentation(tmp_path: Path) -> None:
    path = ROOT / "scripts/build_pages.py"
    spec = importlib.util.spec_from_file_location("build_pages", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = tmp_path / "site"
    site_root = module.build(output)
    assert (site_root / "index.html").is_file()
    content = (site_root / "index.html").read_text(encoding="utf-8")
    assert "Grounded Hyperset Theory" in content
    assert "Accessible Pointed Graphs" in content


def test_pages_builder_refuses_to_merge_into_existing_content(tmp_path: Path) -> None:
    path = ROOT / "scripts/build_pages.py"
    spec = importlib.util.spec_from_file_location("build_pages_safety", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = tmp_path / "site"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")
    with pytest.raises(module.PagesBuildError, match="refusing to merge into non-empty Pages output"):
        module.build(output)
    assert marker.read_text(encoding="utf-8") == "keep\n"
