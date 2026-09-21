#!/usr/bin/env python3
"""Build the grounded-hyperset-theory research paper PDF from LaTeX source.

Compiles paper/grounded_hyperset_theory.tex into paper/grounded_hyperset_theory.pdf.
Requires pdflatex on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
DEFAULT_TEX_FILE = "paper.tex"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=DEFAULT_TEX_FILE, help="LaTeX source file to compile")
    args = parser.parse_args()

    tex_file = args.target
    pdf_file = Path(tex_file).stem + ".pdf"

    if not shutil.which("pdflatex"):
        raise SystemExit("pdflatex executable not found on PATH.")

    for pass_num in range(1, 3):
        print(f"LaTeX pass {pass_num}/2 (timeout 90s)...", flush=True)
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            tex_file,
        ]
        result = subprocess.run(cmd, cwd=PAPER, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            print("pdflatex STDOUT:\n", result.stdout)
            print("pdflatex STDERR:\n", result.stderr)
            raise SystemExit(f"pdflatex failed with exit code {result.returncode}")

    target_pdf = PAPER / pdf_file
    if not target_pdf.exists():
        raise SystemExit(f"Expected output {target_pdf} was not generated.")

    log_file = PAPER / (Path(tex_file).stem + ".log")
    if log_file.exists():
        log = log_file.read_text(encoding="utf-8", errors="replace")
        issues = [
            line
            for line in log.splitlines()
            if any(term in line for term in ("Overfull", "undefined", "Missing character", "LaTeX Warning"))
            and "infwarerr" not in line
        ]
        if issues:
            raise SystemExit("Manuscript needs inspection:\n" + "\n".join(issues))

    print(f"Successfully generated {target_pdf} ({target_pdf.stat().st_size:,} bytes).")


if __name__ == "__main__":
    main()
