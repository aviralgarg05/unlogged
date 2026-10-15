"""Real work events, pulled from a GitHub repository.

The evaluation in this repo runs on eight events its author wrote. That makes every number
it reports unfalsifiable: an arm scoring 100% against a thread written by the same person
who wrote the arm has demonstrated nothing. This pulls the same shape of event from work
that actually happened — pull requests, their review comments, issues and issue comments —
so the comparison is a measurement rather than a demonstration.

Three things the thread has to preserve to be worth adjudicating:

* WHO SAID IT. A request from the client and a commit by the contractor are different kinds
  of event, and the whole product turns on not billing the first as though it were the second.
* WHEN. Events are ordered, because a request and the work answering it are two events and
  the order is what tells them apart.
* THE WORDS. Verbatim, because a verdict has to quote the span it relied on, and a
  paraphrase cannot be audited against the contract.

Recorded responses replay with no token, on the same terms as the PayPal cassettes: the
keyless path is the one a judge uses, so it cannot depend on an account.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from unlogged import cassette
from unlogged.scope.models import Source, WorkEvent

log = structlog.get_logger(__name__)

API = "https://api.github.com"
# Bodies reach a model prompt and an invoice line. Past a few hundred characters a PR
# description is a changelog, not a statement of what was asked for.
MAX_TEXT = 700

# Review bots and coverage reporters are a real part of a repository and no part of an
# engagement: a client thread has no coderabbit in it. Left in, they outnumber the humans
# three to two and the evaluation becomes a measurement of how well an arm ignores robots.
BOTS = (
    "codecov-commenter",
    "dependabot",
    "github-actions",
    "renovate",
    "pre-commit-ci",
    # Reviews as "Copilot", with no [bot] suffix, and produced 72 of 365 events on the first
    # repository this was pointed at. A suffix check alone is not enough.
    "Copilot",
    "sourcery-ai",
    "codiumai-pr-agent",
)


def is_bot(login: str) -> bool:
    return login.endswith("[bot]") or login in BOTS


def _clip(text: str | None) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1].rstrip() + "…"


# What a recording keeps. GitHub answers a pull request with something over a hundred
# fields, nested head and base repository objects included; this code reads six of them.
# Recording the rest cost six times the size of the whole repository in JSON nobody would
# ever open, and made a cassette unreadable to the judge it exists for. A recording is
# therefore a record of what was used, not of everything that was returned — which is also
# why adding a field to `events` means re-recording rather than re-reading.
KEEP = {
    "pull": ("number", "title", "body", "created_at", "html_url", "state", "merged_at"),
    "detail": ("number", "changed_files", "additions", "deletions"),
    "issue": ("number", "title", "body", "created_at", "html_url", "state"),
    "comment": ("id", "body", "created_at", "html_url"),
    "review": ("id", "body", "state", "submitted_at", "html_url"),
}


def _slim(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    out = {k: item[k] for k in fields if k in item}
    if isinstance(out.get("body"), str):
        # Clipped here as well as on the way out: three quarters of the characters GitHub
        # returns are past the point this product stops reading, and a committed recording
        # should not carry them.
        out["body"] = _clip(out["body"])
    if "user" in item and isinstance(item["user"], dict):
        out["user"] = {"login": item["user"].get("login")}
    if "pull_request" in item:
        # Only its presence matters: it marks an issue that is really a pull request.
        out["pull_request"] = {}
    return out


def project(path: str, body: Any) -> Any:
    """Keep the fields `events` reads and drop the rest before anything is written down."""
    if isinstance(body, dict):
        return _slim(body, KEEP["detail"] + KEEP["pull"])
    if not isinstance(body, list):
        return body
    if path.endswith("/reviews"):
        fields = KEEP["review"]
    elif path.endswith("/comments"):
        fields = KEEP["comment"]
    elif path.endswith("/issues"):
        fields = KEEP["issue"]
    else:
        fields = KEEP["pull"]
    return [_slim(i, fields) for i in body if isinstance(i, dict)]


class GitHubError(RuntimeError):
    def __init__(self, status: int, body: str):
        self.status, self.body = status, body
        super().__init__(f"GitHub {status}: {body[:300]}")


class GitHub:
    """Read-only. Nothing here writes to a repository, and nothing needs write scope.

    A token is optional: public repositories answer unauthenticated at 60 requests an hour,
    which is enough to pull one engagement. `GITHUB_TOKEN=$(gh auth token)` works if the
    `gh` CLI is already signed in, and a fine-grained token with read access to a single
    repository is enough for a private one.
    """

    def __init__(
        self,
        repo: str,
        *,
        token: str | None = None,
        replay: bool = True,
        timeout: float = 30.0,
    ):
        if "/" not in repo:
            raise ValueError(f"repo must be owner/name, got {repo!r}")
        self.repo = repo
        self.token = token
        self.replay = replay
        self.tape = cassette.Tape()
        self._http = httpx.Client(timeout=timeout)

    def __enter__(self) -> GitHub:
        return self

    def __exit__(self, *exc: object) -> None:
        self._http.close()

    # -- transport ----------------------------------------------------------

    def _get(self, path: str, **params: Any) -> Any:
        key = cassette.key({"gh": path, "q": params})

        if self.replay or not self.token:
            rec = self.tape.replay(key)
            if rec is None:
                raise GitHubError(
                    0,
                    f"No cassette for GET {path} ({key}). Run with UNLOGGED_REPLAY=0 and a "
                    f"GITHUB_TOKEN, or pick a repository whose thread is already recorded.",
                )
            if rec["status"] >= 400:
                raise GitHubError(rec["status"], str(rec["body"]))
            return rec["body"]

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {self.token}",
        }
        r = self._http.get(f"{API}{path}", headers=headers, params=params)
        log.debug("github", path=path, status=r.status_code)
        if r.status_code >= 400:
            raise GitHubError(r.status_code, r.text)
        body = project(path, r.json())
        self.tape.record(key, {"status": r.status_code, "body": body})
        return body

    def _paged(self, path: str, *, pages: int = 3, **params: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for page in range(1, pages + 1):
            batch = self._get(path, per_page=100, page=page, **params)
            if not isinstance(batch, list) or not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
        return out

    # -- events -------------------------------------------------------------

    def events(self, *, pr_detail: int = 40, include_bots: bool = False) -> list[WorkEvent]:
        """Every pull request, issue and comment on the repository, oldest first.

        `pr_detail` bounds how many pull requests get a second call for their diff stats.
        Those stats are what make "this work was done" checkable rather than asserted, so
        they are worth the requests, but not unboundedly.
        """
        owner_repo = self.repo
        pulls = self._paged(f"/repos/{owner_repo}/pulls", state="all")
        issues = self._paged(f"/repos/{owner_repo}/issues", state="all")
        review_comments = self._paged(f"/repos/{owner_repo}/pulls/comments")
        issue_comments = self._paged(f"/repos/{owner_repo}/issues/comments")

        # Diff stats need a call per pull request, and they are evidence rather than
        # structure: without them an event still says what was asked for and by whom. A rate
        # limit, a permission or a missing recording therefore costs detail, not the thread.
        stats: dict[int, dict[str, Any]] = {}
        reviews: list[dict[str, Any]] = []
        missed = 0
        for pr in sorted(pulls, key=lambda p: p["number"], reverse=True)[:pr_detail]:
            n = pr["number"]
            try:
                stats[n] = self._get(f"/repos/{owner_repo}/pulls/{n}")
            except GitHubError:
                missed += 1
            try:
                reviews += self._get(f"/repos/{owner_repo}/pulls/{n}/reviews")
            except GitHubError:
                missed += 1
        if missed:
            log.warning("github_pr_detail_unavailable", repo=owner_repo, pull_requests=missed)

        events: list[WorkEvent] = []

        for pr in pulls:
            n = pr["number"]
            d = stats.get(n)
            body = _clip(pr.get("body"))
            shape = ""
            if d:
                shape = (
                    f" {d.get('changed_files', 0)} files changed, "
                    f"+{d.get('additions', 0)} -{d.get('deletions', 0)}."
                )
            events.append(
                WorkEvent(
                    id=f"pr-{n}",
                    source=Source.GITHUB,
                    author=(pr.get("user") or {}).get("login", "unknown"),
                    occurred_at=pr["created_at"],
                    text=_clip(f"PR #{n}: {pr['title']}.{shape} {body}"),
                    permalink=pr.get("html_url"),
                )
            )

        for issue in issues:
            # GitHub returns pull requests from the issues endpoint too; they are already in.
            if "pull_request" in issue:
                continue
            n = issue["number"]
            events.append(
                WorkEvent(
                    id=f"issue-{n}",
                    source=Source.GITHUB,
                    author=(issue.get("user") or {}).get("login", "unknown"),
                    occurred_at=issue["created_at"],
                    text=_clip(f"Issue #{n}: {issue['title']}. {_clip(issue.get('body'))}"),
                    permalink=issue.get("html_url"),
                )
            )

        for r in reviews:
            # A review submission is the verdict on the whole change — "CHANGES_REQUESTED:
            # Solve the issues" — and it is a different event from a comment on a line of
            # code. These were missing entirely: the endpoint that returns review comments
            # does not return the reviews, so every "this is not what I asked for" was
            # dropped from a corpus built to find exactly those.
            if not (r.get("body") or "").strip():
                continue
            events.append(
                WorkEvent(
                    id=f"review-{r['id']}",
                    source=Source.GITHUB,
                    author=(r.get("user") or {}).get("login", "unknown"),
                    occurred_at=r["submitted_at"],
                    text=_clip(f"Review ({r.get('state', 'COMMENTED')}): {r.get('body')}"),
                    permalink=r.get("html_url"),
                )
            )

        for c in review_comments:
            events.append(
                WorkEvent(
                    id=f"inline-{c['id']}",
                    source=Source.GITHUB,
                    author=(c.get("user") or {}).get("login", "unknown"),
                    occurred_at=c["created_at"],
                    text=_clip(f"Review comment: {c.get('body')}"),
                    permalink=c.get("html_url"),
                )
            )

        for c in issue_comments:
            events.append(
                WorkEvent(
                    id=f"comment-{c['id']}",
                    source=Source.GITHUB,
                    author=(c.get("user") or {}).get("login", "unknown"),
                    occurred_at=c["created_at"],
                    text=_clip(f"Comment: {c.get('body')}"),
                    permalink=c.get("html_url"),
                )
            )

        if not include_bots:
            events = [e for e in events if not is_bot(e.author)]

        # Oldest first: a request and the work that answers it are two events, and which came
        # first is the whole difference between billing the work and billing the ask twice.
        events.sort(key=lambda e: (e.occurred_at, e.id))
        return events
