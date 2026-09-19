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
TEX_FILE = "grounded_hyperset_theory.tex"
PDF_FILE = "grounded_hyperset_theory.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    if not shutil.which("pdflatex"):
        raise SystemExit("pdflatex executable not found on PATH.")

    for pass_num in range(1, 3):
        print(f"LaTeX pass {pass_num}/2 (timeout 90s)...", flush=True)
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            TEX_FILE,
        ]
        result = subprocess.run(cmd, cwd=PAPER, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            print("pdflatex STDOUT:\n", result.stdout)
            print("pdflatex STDERR:\n", result.stderr)
            raise SystemExit(f"pdflatex failed with exit code {result.returncode}")

    target_pdf = PAPER / PDF_FILE
    if not target_pdf.exists():
        raise SystemExit(f"Expected output {target_pdf} was not generated.")

    print(f"Successfully generated {target_pdf} ({target_pdf.stat().st_size:,} bytes).")


if __name__ == "__main__":
    main()
