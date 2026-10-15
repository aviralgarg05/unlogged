"""The GitHub source, which exists to make the evaluation falsifiable.

Everything here runs against recorded or synthetic payloads. A test that needed a token
would be a test the judge path cannot run, which is the one thing this project will not do.
"""

from __future__ import annotations

import json

import pytest

from unlogged import cassette
from unlogged.scope.models import Source
from unlogged.sources.github import MAX_TEXT, GitHub, GitHubError, is_bot


def _record(tape: cassette.Tape, path: str, body, **params) -> None:
    tape.record(
        cassette.key({"gh": path, "q": {"per_page": 100, "page": 1, **params}}),
        {"status": 200, "body": body},
    )


def _repo(tmp_path, pulls=(), issues=(), review=(), comments=(), details=(), reviews=()):
    gh = GitHub("o/r", replay=True)
    gh.tape = cassette.Tape(tmp_path)
    _record(gh.tape, "/repos/o/r/pulls", list(pulls), state="all")
    _record(gh.tape, "/repos/o/r/issues", list(issues), state="all")
    _record(gh.tape, "/repos/o/r/pulls/comments", list(review))
    _record(gh.tape, "/repos/o/r/issues/comments", list(comments))
    for d in details:
        gh.tape.record(
            cassette.key({"gh": f"/repos/o/r/pulls/{d['number']}", "q": {}}),
            {"status": 200, "body": d},
        )
    for pr in pulls:
        gh.tape.record(
            cassette.key({"gh": f"/repos/o/r/pulls/{pr['number']}/reviews", "q": {}}),
            {"status": 200, "body": list(reviews)},
        )
    return gh


PR = {
    "number": 312,
    "title": "handle PSP timeout and 3DS re-challenge on checkout submit",
    "body": "Adds retry with backoff.",
    "created_at": "2026-10-03T11:10:00Z",
    "user": {"login": "aviral"},
    "html_url": "https://github.com/o/r/pull/312",
}


def test_a_pull_request_becomes_an_event_that_carries_its_diff_stats(tmp_path):
    """ "4 files changed, +211 -18" is what makes "this work was done" checkable instead of
    asserted, and it is the evidence a disputed invoice line rests on."""
    detail = {**PR, "changed_files": 4, "additions": 211, "deletions": 18}
    gh = _repo(tmp_path, pulls=[PR], details=[detail])

    (event,) = gh.events()

    assert event.id == "pr-312"
    assert event.source is Source.GITHUB
    assert event.author == "aviral"
    assert "PR #312" in event.text
    assert "4 files changed, +211 -18" in event.text
    assert event.permalink == "https://github.com/o/r/pull/312"
    # What the client reads beside the invoice line.
    assert event.provenance == "github 03 Oct"


def test_events_are_ordered_oldest_first(tmp_path):
    """A request and the work answering it are two events. Which came first is the whole
    difference between billing the work once and billing the ask as though it were work."""
    ask = {
        "id": 900,
        "body": "Can you also surface the decline reason?",
        "created_at": "2026-10-01T09:00:00Z",
        "user": {"login": "client"},
    }
    gh = _repo(tmp_path, pulls=[PR], comments=[ask])

    ids = [e.id for e in gh.events()]

    assert ids == ["comment-900", "pr-312"]


def test_pull_requests_are_not_counted_twice_through_the_issues_endpoint(tmp_path):
    """GitHub returns pull requests from /issues as well. Counted twice, every PR would be
    adjudicated twice and could be billed twice."""
    as_issue = {
        "number": 312,
        "title": PR["title"],
        "body": "",
        "created_at": PR["created_at"],
        "user": {"login": "aviral"},
        "pull_request": {"url": "..."},
    }
    gh = _repo(tmp_path, pulls=[PR], issues=[as_issue])

    assert [e.id for e in gh.events()] == ["pr-312"]


def test_bots_are_left_out_unless_asked_for(tmp_path):
    bot = {
        "id": 5,
        "body": "Coverage decreased by 0.2%",
        "created_at": "2026-10-04T09:00:00Z",
        "user": {"login": "codecov-commenter"},
    }
    review_bot = {
        "id": 6,
        "body": "Consider extracting this",
        "created_at": "2026-10-04T10:00:00Z",
        "user": {"login": "coderabbitai[bot]"},
    }

    gh = _repo(tmp_path, pulls=[PR], comments=[bot], review=[review_bot])
    assert [e.id for e in gh.events()] == ["pr-312"]

    gh = _repo(tmp_path, pulls=[PR], comments=[bot], review=[review_bot])
    assert len(gh.events(include_bots=True)) == 3


def test_is_bot_recognises_the_suffix_and_the_named_reporters():
    assert is_bot("coderabbitai[bot]") and is_bot("codecov-commenter")
    assert not is_bot("aviralgarg05") and not is_bot("robotics-student")


def test_long_bodies_are_clipped_before_they_reach_a_prompt_or_an_invoice(tmp_path):
    gh = _repo(tmp_path, pulls=[{**PR, "body": "x" * 5000}])

    (event,) = gh.events()

    assert len(event.text) <= MAX_TEXT
    assert event.text.endswith("…")


def test_whitespace_in_a_body_is_normalised(tmp_path):
    gh = _repo(tmp_path, pulls=[{**PR, "body": "line one\n\n   line two\t\tend"}])

    (event,) = gh.events()

    assert "line one line two end" in event.text


def test_a_missing_recording_says_how_to_make_one_rather_than_failing_blankly(tmp_path):
    gh = GitHub("o/r", replay=True)
    gh.tape = cassette.Tape(tmp_path)

    with pytest.raises(GitHubError) as e:
        gh.events()

    assert "No cassette" in str(e.value)
    assert "GITHUB_TOKEN" in str(e.value)


def test_a_repo_that_is_not_owner_slash_name_is_refused_immediately():
    with pytest.raises(ValueError):
        GitHub("agentunit")


def test_the_recorded_agentunit_thread_replays_with_no_token():
    """The real thread this project uses, read back from what is committed.

    If this fails, a judge with no GitHub account cannot reproduce the evaluation, which is
    the whole reason the recordings exist.
    """
    with GitHub("aviralgarg05/agentunit", replay=True) as gh:
        events = gh.events(pr_detail=12)

    assert len(events) > 100
    assert {e.source for e in events} == {Source.GITHUB}
    # More than one voice, or there is no client in the thread and nothing to adjudicate.
    assert len({e.author for e in events}) > 5
    assert events == sorted(events, key=lambda e: (e.occurred_at, e.id))
    assert all(e.text.strip() for e in events)
    assert len({e.id for e in events}) == len(events)
    # Nothing a bot said reached the thread.
    assert not [e for e in events if is_bot(e.author)]


def test_every_recorded_event_round_trips_through_its_own_model():
    with GitHub("aviralgarg05/agentunit", replay=True) as gh:
        events = gh.events(pr_detail=12)

    for e in events[:20]:
        assert json.loads(e.model_dump_json())["id"] == e.id


def test_a_missing_diff_stat_costs_detail_not_the_thread(tmp_path):
    """Stats need a call per pull request. A rate limit on the twentieth of them should not
    throw away the nineteen events already in hand."""
    gh = _repo(tmp_path, pulls=[PR])  # no detail recorded for #312

    (event,) = gh.events()

    assert event.id == "pr-312"
    assert "files changed" not in event.text
    assert PR["title"] in event.text


def test_a_reviewer_bot_without_the_suffix_is_still_a_bot():
    """GitHub's own reviewer appears as plain "Copilot" and produced 72 of the 365 events on
    the first repository this was pointed at. A suffix check alone would have let it through
    and the evaluation would have been measuring how well an arm ignores a robot."""
    assert is_bot("Copilot")
    assert not is_bot("copilot-user")


def test_a_review_submission_is_its_own_event(tmp_path):
    """ "CHANGES_REQUESTED: Solve the issues" is the client saying this is not what was asked
    for, and it is a different event from a comment on a line of code. The endpoint that
    returns review comments does not return reviews, so every one of these was dropped — from
    a corpus built to find exactly them.
    """
    submission = {
        "id": 77,
        "body": "Solve the issues",
        "state": "CHANGES_REQUESTED",
        "submitted_at": "2026-10-04T08:00:00Z",
        "user": {"login": "client"},
        "html_url": "https://github.com/o/r/pull/312#pullrequestreview-77",
    }
    gh = _repo(tmp_path, pulls=[PR], reviews=[submission])

    review = next(e for e in gh.events() if e.id == "review-77")

    assert "CHANGES_REQUESTED" in review.text
    assert "Solve the issues" in review.text
    assert review.author == "client"


def test_an_empty_review_body_is_not_an_event(tmp_path):
    """Approving with no words says nothing about scope and would pad the corpus."""
    empty = {
        "id": 78,
        "body": "",
        "state": "APPROVED",
        "submitted_at": "2026-10-04T08:00:00Z",
        "user": {"login": "client"},
    }
    gh = _repo(tmp_path, pulls=[PR], reviews=[empty])

    assert [e.id for e in gh.events()] == ["pr-312"]


def test_a_review_submission_and_a_line_comment_do_not_share_an_id_space(tmp_path):
    """Both arrive with GitHub ids drawn from different sequences. Collapsed under one prefix
    they could collide, and two different events would silently become one."""
    submission = {
        "id": 5,
        "body": "Solve the issues",
        "state": "CHANGES_REQUESTED",
        "submitted_at": "2026-10-04T08:00:00Z",
        "user": {"login": "client"},
    }
    line_comment = {
        "id": 5,
        "body": "Consider extracting this",
        "created_at": "2026-10-04T09:00:00Z",
        "user": {"login": "client"},
    }
    gh = _repo(tmp_path, pulls=[PR], reviews=[submission], review=[line_comment])

    assert sorted(e.id for e in gh.events()) == ["inline-5", "pr-312", "review-5"]
