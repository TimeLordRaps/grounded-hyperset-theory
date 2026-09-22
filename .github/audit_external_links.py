"""Audit every external link in every tracked document.

Shared across the family, so it may name no repository's layout: the file
list comes from `git ls-files`, never a hardcoded `docs/`.

Verdict policy. A weekly audit that fails on transient network noise trains
its readers to ignore it, and an audit nobody reads is worse than none. So a
link fails the run only when the far side answered definitively that it is
gone -- 404, 410, or a hostname that does not resolve. Timeouts, 5xx, 429,
and TLS problems are reported in the artifact and do not fail: they are
statements about today's network, not about the link.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import pathlib
import re
import socket
import string
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# Bare-URL and markdown-target forms both appear in these trees.
# Characters that end a URL in prose: whitespace, then the closers that
# markdown, tables, and quoting wrap them in. `)` is deliberately NOT one of
# them -- `en.wikipedia.org/wiki/Foo_(bar)` is a real URL -- so an unbalanced
# trailing paren is stripped below instead. Spelled by code point because
# a backslash in this line does not survive every way this file gets written.
_STOP = str().join(
    chr(c) for c in (32, 9, 10, 13, 60, 62, 34, 39, 93, 125, 124, 92, 96)
)
URL = re.compile("https?://[^" + re.escape(_STOP) + "]+")
# Trailing punctuation belongs to the prose, not to the URL. `*` is here
# because markdown emphasis closes after the link -- `[text](url)**` -- and
# stripping it has to interleave with the unbalanced-paren strip below, or
# `url)**` ends in `*`, the paren is never reached, and a live page is
# reported gone. Measured: that one ordering mistake accounted for four of
# the seven "dead" links in the first run across the fleet.
TRAILING = ".,;:!?*'\""

# A backslash before punctuation is markdown's escape and means the character
# itself. Built through `re.escape` and `chr(92)` rather than written out: a
# literal backslash in this file does not survive every way the file gets
# edited, and the failure is silent -- the pattern still compiles, and matches
# nothing.
_ESCAPED = re.compile(
    re.escape(chr(92)) + "([" + re.escape(string.punctuation) + "])"
)

AGENT = "Mozilla/5.0 (compatible; external-link-audit/1.0; +https://github.com)"
GONE = {404, 410}

# Documents that record a moment rather than assert a live surface. A dated
# archive naming a URL that has since died is an accurate record, and
# repointing it would falsify the record.
EXEMPT_DIRECTORY = re.compile(r"(^|/)(archive|references|vendor|\.venv|node_modules)(/|$)")


def tracked_documents() -> list[str]:
    # splitlines(), never split(): a tracked path may contain a space.
    names = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    wanted = [
        n
        for n in names
        if n.endswith((".md", ".markdown", ".rst", ".txt"))
        and not EXEMPT_DIRECTORY.search(n)
    ]
    # A path can be in the index and not on disk -- a working tree mid-edit, a
    # sparse checkout. CI checks out everything, so this only fires locally;
    # it is counted and reported rather than swallowed, because auditing fewer
    # documents than the repository tracks is the failure this job exists to
    # catch, and a traceback says less than the count does.
    present = [n for n in wanted if pathlib.Path(n).is_file()]
    if len(present) != len(wanted):
        print(
            f"note: {len(wanted) - len(present)} tracked document(s) absent "
            "from disk, skipped",
            file=sys.stderr,
        )
    return present


def unescape(body: str) -> str:
    """Undo markdown's backslash escapes before any URL is read out.

    A document generated from a research tool writes the link text as an
    escaped copy of the target: `[https://host/a\\_b.pdf](https://host/a_b.pdf)`.
    A backslash ends a URL, so the escaped copy truncates at the first `\\_`
    and the audit reports a live page gone -- five of the seven such reports
    in the first fleet run were this one pattern in one document. A renderer
    would drop the backslash; so does this, and only before punctuation,
    which is the only place markdown gives it that meaning.
    """
    return _ESCAPED.sub(r"\1", body)


def normalise(raw: str) -> str:
    """Drop the prose a URL was written inside, and nothing else.

    One loop, not two passes: each strip can expose the other's target.
    `](url)` leaves the closing paren out via the character class, but a URL
    may legitimately end in one -- `wiki/Foo_(bar)` -- so only an unbalanced
    paren is dropped, and only after trailing emphasis has been taken off.
    """
    url = raw
    while True:
        shortened = url.rstrip(TRAILING)
        if shortened.endswith(")") and shortened.count("(") < shortened.count(")"):
            shortened = shortened[:-1]
        if shortened == url:
            return url
        url = shortened


def collect(names: list[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name in names:
        body = unescape(
            pathlib.Path(name).read_text(encoding="utf-8", errors="replace")
        )
        for raw in URL.findall(body):
            url = normalise(raw)
            if not urllib.parse.urlparse(url).netloc:
                continue
            found.setdefault(url, [])
            if name not in found[url]:
                found[url].append(name)
    return found


def probe(url: str, retries: int) -> dict:
    last: dict = {}
    for attempt in range(retries + 1):
        for method in ("HEAD", "GET"):
            request = urllib.request.Request(url, method=method, headers={"User-Agent": AGENT})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return {"status": response.status, "verdict": "ok", "method": method}
            except urllib.error.HTTPError as error:
                last = {"status": error.code, "method": method}
                if error.code in GONE:
                    return {**last, "verdict": "gone"}
                if error.code in (405, 501) and method == "HEAD":
                    continue  # the host refuses HEAD; GET is the real answer
                last["verdict"] = "unreachable"
                break
            except urllib.error.URLError as error:
                reason = error.reason
                resolves = not (
                    isinstance(reason, socket.gaierror)
                    and reason.errno in (socket.EAI_NONAME, getattr(socket, "EAI_NODATA", -5))
                )
                last = {
                    "status": None,
                    "method": method,
                    "error": str(reason),
                    "verdict": "unreachable" if resolves else "gone",
                }
                if not resolves:
                    return last
                break
            except Exception as error:  # noqa: BLE001 - any transport fault is "unreachable"
                last = {"status": None, "method": method, "error": str(error), "verdict": "unreachable"}
                break
    return last or {"status": None, "verdict": "unreachable"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="external-links.json")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--workers", type=int, default=8)
    options = parser.parse_args()

    documents = tracked_documents()
    links = collect(documents)
    results = {}
    if links:
        with concurrent.futures.ThreadPoolExecutor(max_workers=options.workers) as pool:
            futures = {pool.submit(probe, url, options.retries): url for url in sorted(links)}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                results[url] = {**future.result(), "cited_by": links[url]}

    gone = sorted(u for u, r in results.items() if r.get("verdict") == "gone")
    unreachable = sorted(u for u, r in results.items() if r.get("verdict") == "unreachable")
    report = {
        "documents_scanned": len(documents),
        "links_found": len(links),
        "gone": gone,
        "unreachable": unreachable,
        "results": dict(sorted(results.items())),
    }
    pathlib.Path(options.report).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"scanned {len(documents)} tracked documents, {len(links)} distinct external links")
    for url in unreachable:
        print(f"  [unreachable, not failing] {url}  <- {', '.join(results[url]['cited_by'][:3])}")
    for url in gone:
        print(f"  [GONE] {url}  <- {', '.join(results[url]['cited_by'])}")
    if gone:
        print(f"{len(gone)} link(s) answered definitively gone")
        return 1
    print("no link answered definitively gone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
