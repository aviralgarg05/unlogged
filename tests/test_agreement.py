"""The agreement statistics, checked against cases whose answers are known.

A statistic a project computes about itself is worth nothing unless the implementation is
right, and these are easy to get subtly wrong — a kappa that divides by the wrong marginal
still produces a plausible-looking number between 0 and 1.
"""

from __future__ import annotations

import pytest

from unlogged.eval.agreement import score


def _sets(pairs):
    first = {f"e{i}": a for i, (a, _) in enumerate(pairs)}
    second = {f"e{i}": b for i, (_, b) in enumerate(pairs)}
    return first, second


def test_cohens_kappa_matches_the_worked_example():
    """The standard 2x2 illustration: 20/5/10/15 gives Po=0.70, Pe=0.50, kappa=0.40."""
    pairs = [("A", "A")] * 20 + [("A", "B")] * 5 + [("B", "A")] * 10 + [("B", "B")] * 15

    result = score(*_sets(pairs))

    assert result.n == 50
    assert round(result.raw, 4) == 0.70
    assert round(result.kappa, 4) == 0.40


def test_perfect_agreement_is_one():
    result = score(*_sets([("A", "A"), ("B", "B"), ("C", "C"), ("A", "A")]))

    assert result.raw == 1.0
    assert result.kappa == 1.0
    assert result.ac1 == 1.0
    assert result.disagreements == []


def test_total_disagreement_is_negative():
    """Worse than chance, and the sign has to show it rather than clamping at zero."""
    result = score(*_sets([("A", "B")] * 10 + [("B", "A")] * 10))

    assert result.raw == 0.0
    assert result.kappa < 0


def test_the_kappa_paradox_is_why_ac1_is_reported_too():
    """When one category dominates, kappa collapses although the raters agree on almost
    everything. Reporting kappa alone would understate agreement exactly where the categories
    are skewed — which is the shape of this project's own data, about half of it noise.
    """
    pairs = [("noise", "noise")] * 90 + [("noise", "included")] * 5 + [("included", "noise")] * 5

    result = score(*_sets(pairs))

    assert result.raw == 0.90
    assert result.kappa < 0.1  # chance correction eats it
    assert result.ac1 > 0.85  # agreement, as a reader would understand the word


def test_events_only_one_pass_labelled_are_not_counted_as_disagreement():
    """A reader who never looked at an event has not disagreed about it, and counting silence
    as a verdict would make the statistic depend on how much each pass chose to cover."""
    first = {"e1": "noise", "e2": "included", "e3": "noise"}
    second = {"e1": "noise", "e2": "included"}

    result = score(first, second)

    assert result.n == 2
    assert result.raw == 1.0


def test_no_shared_event_is_an_error_not_a_score_of_zero():
    with pytest.raises(ValueError, match="no event in common"):
        score({"e1": "noise"}, {"e2": "noise"})


def test_the_disagreements_are_listed_so_a_reader_can_see_if_they_are_one_judgement():
    """Six disagreements that are all the same call mean something different from six
    scattered ones, and only the list shows which."""
    first = {"e1": "noise", "e2": "noise", "e3": "included"}
    second = {"e1": "billable_extra", "e2": "billable_extra", "e3": "included"}

    result = score(first, second)

    assert result.disagreements == [
        ("e1", "noise", "billable_extra"),
        ("e2", "noise", "billable_extra"),
    ]


def test_this_projects_own_two_passes_reproduce_the_published_figures():
    """The numbers quoted in docs/CORPUS.md, from the committed label sets."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "fixtures" / "agreement"

    def load(name):
        out = {}
        for line in (root / name).read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                out[f"{row['issue']}:{row['event_id']}"] = row["call"]
        return out

    result = score(load("round1.jsonl"), load("round2.jsonl"))

    assert result.n == 31
    assert round(result.raw, 3) == 0.806
    assert round(result.kappa, 3) == 0.719
    assert round(result.ac1, 3) == 0.749
    # Half of the disagreements are one judgement on one thread: whether a comment reporting
    # completed out-of-scope work is noise or the billable work itself.
    same = [d for d in result.disagreements if d[1] == "noise" and d[2] == "billable_extra"]
    assert len(same) == 3
