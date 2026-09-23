#!/usr/bin/env python3
"""Terminology: JavaScript Object Notation (JSON); pull request (PR).

Refuse a push that leaves a pull-request description word for word unchanged.

A description is written for the head it describes, so every push of a new head has
to come with a revised description. This check compares the description with the one
that was in force when the pull request's current head was pushed. If the two are
the same word for word, the push is refused. Only words are compared: an edit that
changes nothing but spacing or line endings is not a revision.

Nothing is stored. GitHub keeps every revision of a description with the moment it
was made, and the first pull-request workflow run on a head marks the moment that
head was pushed. Later runs on the same head come from edits, so the first is the
push. The revision in force at that moment is the reference.

Before a push, the check judges the live description against the current head's
push. After one, `--pushed HEAD` judges the push that made HEAD the head: the
description in force at that push against the one in force at the push before it.
That verdict is fixed once both pushes are made, so it comes out the same on every
later event, and an edit made afterwards cannot clear it. Only another push, with a
revised description, can. The push before is the latest one recorded among the pull
request's runs; a head no pull-request run ever saw is not recorded.

A revised description is not thereby a correct one. The `describes-head` check holds
what the description says to the head; this check establishes only that the
description was revised since the last push.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

PULL_REQUEST_EVENTS = frozenset({"pull_request", "pull_request_target"})
REVISIONS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      userContentEdits(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { editedAt deletedAt diff }
      }
    }
  }
}
"""


class Unanswered(Exception):
    """A question GitHub did not answer. It is not a no."""


def words(text: str) -> list[str]:
    return text.split()


def _instant(moment: str) -> datetime:
    return datetime.fromisoformat(moment.replace("Z", "+00:00"))


def pushed_at(runs: list[dict], number: int) -> str | None:
    """The moment a head was pushed to pull request `number`: its first run there."""

    moments = [
        run["created_at"] for run in runs
        if run.get("event") in PULL_REQUEST_EVENTS
        and (not run.get("pull_requests") or number in run["pull_requests"])
    ]
    return min(moments, key=_instant) if moments else None


def pushes(runs: list[dict], number: int, head_repository: str) -> dict[str, str]:
    """Each head of pull request `number` with the moment it was pushed.

    `runs` are the runs on the pull request's head branch. A branch of the same name
    in another repository is another branch, so runs from it are not pushes here.
    """

    moments: dict[str, str] = {}
    for run in runs:
        if run.get("head_repository") != head_repository:
            continue
        moment = pushed_at([run], number)
        head = run["head_sha"]
        if moment and (head not in moments or _instant(moment) < _instant(moments[head])):
            moments[head] = moment
    return moments


def in_force(revisions: list[dict], moment: str) -> dict | None:
    """The revision in force at `moment`: the latest one made at or before it."""

    earlier = [revision for revision in revisions
               if _instant(revision["editedAt"]) <= _instant(moment)]
    return max(earlier, key=lambda revision: _instant(revision["editedAt"])) if earlier else None


def _gh(arguments: list[str]) -> str:
    try:
        result = subprocess.run(["gh", *arguments], capture_output=True, text=True,
                                encoding="utf-8", timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise Unanswered(f"gh could not be run: {error}") from error
    if result.returncode != 0:
        raise Unanswered(f"gh {' '.join(arguments[:2])} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def fetch_pull(repository: str, number: int) -> tuple[str, str]:
    """The live description and the current head of a pull request."""

    data = json.loads(_gh(["pr", "view", str(number), "--repo", repository,
                           "--json", "body,headRefOid"]))
    return data.get("body") or "", data["headRefOid"]


def fetch_branch(repository: str, number: int) -> tuple[str, str]:
    """The head branch of a pull request and the repository that holds it."""

    data = json.loads(_gh(["pr", "view", str(number), "--repo", repository, "--json",
                           "headRefName,headRepository,headRepositoryOwner"]))
    return (data["headRefName"],
            f"{data['headRepositoryOwner']['login']}/{data['headRepository']['name']}")


def fetch_runs(repository: str, head: str) -> list[dict]:
    output = _gh([
        "api", "--paginate", f"repos/{repository}/actions/runs?head_sha={head}&per_page=100",
        "--jq", ".workflow_runs[] | {created_at, event, "
                "pull_requests: [.pull_requests[].number]} | @json",
    ])
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def fetch_branch_runs(repository: str, branch: str) -> list[dict]:
    output = _gh([
        "api", "--paginate",
        f"repos/{repository}/actions/runs?branch={quote(branch, safe='')}&per_page=100",
        "--jq", ".workflow_runs[] | {head_sha, created_at, event, "
                "head_repository: .head_repository.full_name, "
                "pull_requests: [.pull_requests[].number]} | @json",
    ])
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def fetch_revisions(repository: str, number: int) -> list[dict]:
    owner, name = repository.split("/", 1)
    revisions: list[dict] = []
    cursor: str | None = None
    while True:
        arguments = ["api", "graphql", "-f", f"query={REVISIONS_QUERY}", "-f", f"owner={owner}",
                     "-f", f"name={name}", "-F", f"number={number}"]
        if cursor:
            arguments += ["-f", f"cursor={cursor}"]
        page = json.loads(_gh(arguments))["data"]["repository"]["pullRequest"]["userContentEdits"]
        revisions.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return revisions
        cursor = page["pageInfo"]["endCursor"]


def check(repository: str, number: int, head: str | None = None,
          body: str | None = None) -> tuple[bool, str]:
    """Return (revised, message) for pull request `number`.

    `head` is the head whose push fixes the reference; by default the pull request's
    current head, the one a push is about to replace. `body` is the description being
    judged; by default the live one.
    """

    if head is None or body is None:
        live_body, current_head = fetch_pull(repository, number)
        head = current_head if head is None else head
        body = live_body if body is None else body
    moment = pushed_at(fetch_runs(repository, head), number)
    if moment is None:
        raise Unanswered(
            f"no pull-request workflow run on {head[:12]} records when it was pushed, so the "
            "description in force then cannot be found. If it was pushed a moment ago, wait "
            "for its first run and try again."
        )
    revisions = fetch_revisions(repository, number)
    if not revisions:
        # Never edited: every copy of the description is the one it was opened with.
        return False, (f"pull request #{number}'s description has never been edited, so it is "
                       f"word for word the one in force when {head[:12]} was pushed ({moment}).")
    reference = _in_force_at_push(revisions, moment, number, head)
    if words(body) == words(reference["diff"]):
        return False, (f"pull request #{number}'s description is word for word the one in force "
                       f"when {head[:12]} was pushed ({moment}; revision of "
                       f"{reference['editedAt']}).")
    return True, (f"pull request #{number}'s description has been revised since {head[:12]} "
                  f"was pushed ({moment}).")


def _in_force_at_push(revisions: list[dict], moment: str, number: int, head: str) -> dict:
    revision = in_force(revisions, moment)
    if revision is None:
        raise Unanswered(f"no revision of pull request #{number}'s description is as old as the "
                         f"push of {head[:12]} ({moment}).")
    if revision.get("deletedAt") or revision.get("diff") is None:
        raise Unanswered(f"the revision of pull request #{number}'s description in force when "
                         f"{head[:12]} was pushed has been deleted from its history.")
    return revision


def check_push(repository: str, number: int, head: str) -> tuple[bool, str]:
    """Return (revised, message) for the push that made `head` pull request `number`'s head.

    Both descriptions compared are the ones in force at a push, never the live one, so
    no edit made after the push of `head` changes the verdict.
    """

    branch, head_repository = fetch_branch(repository, number)
    moments = pushes(fetch_branch_runs(repository, branch), number, head_repository)
    if head not in moments:
        raise Unanswered(
            f"no pull-request workflow run on {head[:12]} records when it was pushed to pull "
            f"request #{number}."
        )
    moment = moments[head]
    earlier = {other: at for other, at in moments.items() if _instant(at) < _instant(moment)}
    if not earlier:
        return True, (f"no push to pull request #{number} is recorded before {head[:12]} "
                      f"({moment}), so there is no earlier description to compare with.")
    previous = max(earlier, key=lambda other: _instant(earlier[other]))
    revisions = fetch_revisions(repository, number)
    if not revisions:
        return False, (f"pull request #{number}'s description has never been edited, so the "
                       f"push of {head[:12]} ({moment}) carried word for word the one in force "
                       f"when {previous[:12]} was pushed ({earlier[previous]}).")
    carried = _in_force_at_push(revisions, moment, number, head)
    reference = _in_force_at_push(revisions, earlier[previous], number, previous)
    if words(carried["diff"]) == words(reference["diff"]):
        return False, (f"the push of {head[:12]} to pull request #{number} ({moment}) carried a "
                       f"description word for word the one in force when {previous[:12]} was "
                       f"pushed ({earlier[previous]}). An edit made since cannot revise a push "
                       f"already made.")
    return True, (f"the push of {head[:12]} to pull request #{number} ({moment}) carried a "
                  f"description revised since {previous[:12]} was pushed ({earlier[previous]}).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="OWNER/NAME holding the pull request")
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument("--head", help="the head whose push fixes the reference; defaults to "
                                       "the pull request's current head")
    parser.add_argument("--body", type=Path, help="judge the description in this file; "
                                                  "defaults to the live description")
    parser.add_argument("--pushed", metavar="HEAD",
                        help="judge the push that made HEAD the head, as it was made; "
                             "excludes --head and --body")
    args = parser.parse_args(argv)
    if args.pushed and (args.head or args.body):
        parser.error("--pushed judges a push already made; --head and --body judge the next one")

    try:
        if args.pushed:
            revised, message = check_push(args.repo, args.pr, args.pushed)
        else:
            body = None if args.body is None else args.body.read_text(encoding="utf-8")
            revised, message = check(args.repo, args.pr, args.head, body)
    except (Unanswered, KeyError, TypeError, ValueError) as error:
        print(f"[PR DESCRIPTION CHANGE] FAIL: {error}")
        return 1
    if revised:
        print(f"[PR DESCRIPTION CHANGE] PASS: {message}")
        return 0
    print(f"[PR DESCRIPTION CHANGE] FAIL: {message}")
    print("  Revise the description for what this push adds, then push again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
