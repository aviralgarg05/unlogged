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


def _published(name):
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "fixtures" / "agreement"
    out = {}
    for line in (root / f"{name}.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            out[f"{row['issue']}:{row['event_id']}"] = row["call"]
    return out


def test_the_model_sits_further_from_both_humans_than_they_sit_from_each_other():
    """The finding that cuts against this project's own headline.

    On the eight authored events the model scores 100%. On 31 events from real pull-request
    threads it agrees with a human reader less often than two human readers agree with each
    other. Both numbers are in the repository and the second one is why the first should not
    be read as a capability claim.
    """
    human = score(_published("round1"), _published("round2"))
    against_first = score(_published("round1"), _published("model"))
    against_second = score(_published("round2"), _published("model"))

    assert human.raw > against_first.raw > against_second.raw
    assert human.kappa > 0.7
    assert against_first.kappa < 0.5
    assert against_second.kappa < 0.35


def test_the_models_error_is_one_direction_not_noise():
    """It collapses everything into "included" rather than being randomly wrong, which is a
    diagnosable failure and not a quality score."""
    import collections

    model = _published("model")
    human = _published("round1")

    calls = collections.Counter(model.values())
    assert calls["included"] == 18
    assert calls["included"] > collections.Counter(human.values())["included"] * 2

    wrong_way = sum(1 for k in model if human[k] != model[k] and model[k] == "included")
    assert wrong_way >= 10


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


def test_the_closure_clause_run_changes_only_the_agreement():
    """The controlled run: same events, same humans, one synthetic clause added. If the events
    ever drift apart the comparison stops isolating anything and silently becomes two
    different experiments.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "fixtures"
    for folder in sorted((root / "nexumdb-closure").iterdir()):
        plain = root / "nexumdb" / folder.name
        assert (folder / "events.jsonl").read_text() == (plain / "events.jsonl").read_text()

        import json

        before = json.loads((plain / "engagement.json").read_text())["clauses"]
        after = json.loads((folder / "engagement.json").read_text())["clauses"]
        assert after[: len(before)] == before
        assert len(after) == len(before) + 1
        added = after[-1]
        assert added["kind"] == "exclusion"
        assert added["text"] == "Work not listed in the tasks above is not part of this issue."


def test_the_model_never_returns_scope_request_on_the_december_events():
    """The finding that matters most, and the one an agreement percentage hides.

    A request and the work answering it are two events; billing both charges the client twice
    for one piece of work, which is why Call.SCOPE_REQUEST exists. Across the 21 events whose
    agreements list no exclusion, both human readers use it five times. The model uses it zero
    times, with and without a closure clause added — while handling the same distinction
    correctly on the authored fixture, which was written in a way that let it succeed.

    Scoped to those 21 deliberately: across all 31 the model does return it once, on a thread
    whose agreement does carry exclusions, and claiming "never" of the whole set would be the
    kind of overstatement this file exists to avoid.
    """
    import collections

    # The closure run covers exactly the December events, so its keys define the span.
    december = set(_published("model-with-closure"))
    assert len(december) == 21

    for arm in ("model", "model-with-closure"):
        calls = collections.Counter(v for k, v in _published(arm).items() if k in december)
        assert calls["scope_request"] == 0, arm

    for human in ("round1", "round2"):
        calls = collections.Counter(v for k, v in _published(human).items() if k in december)
        assert calls["scope_request"] == 5, human

    # And it does use it once across the wider set, which is why the claim is scoped.
    assert collections.Counter(_published("model").values())["scope_request"] == 1


def test_krippendorff_alpha_matches_kappa_on_the_textbook_two_by_two():
    """With two raters, complete data and two categories the two coefficients coincide. A
    statistic that disagreed with kappa here would be wrong, not interesting."""
    from unlogged.eval.agreement import krippendorff_alpha

    pairs = [("A", "A")] * 20 + [("A", "B")] * 5 + [("B", "A")] * 10 + [("B", "B")] * 15

    assert round(krippendorff_alpha(pairs), 4) == 0.40


def test_alpha_is_one_for_perfect_agreement_and_negative_for_systematic_opposition():
    from unlogged.eval.agreement import krippendorff_alpha

    assert krippendorff_alpha([("A", "A"), ("B", "B")]) == 1.0
    assert krippendorff_alpha([("A", "B")] * 10 + [("B", "A")] * 10) < 0


def test_the_interval_is_reported_because_thirty_one_events_is_not_many():
    """0.72 quoted bare invites a reader to treat it as precise. At this sample size the
    interval is nearly half the scale, and the model's agreement with the second reader
    cannot be distinguished from chance at all."""
    human = score(_published("round1"), _published("round2"))
    lo, hi = human.alpha_ci

    assert lo < human.alpha < hi
    assert hi - lo > 0.3

    model = score(_published("round2"), _published("model"))
    assert model.alpha_ci[0] < 0 < model.alpha_ci[1]


def test_the_interval_is_the_same_interval_every_time_it_is_published():
    """Seeded, because a figure in a document has to be the figure a reader reproduces."""
    first = score(_published("round1"), _published("round2")).alpha_ci
    second = score(_published("round1"), _published("round2")).alpha_ci

    assert first == second


def test_per_category_agreement_exposes_what_the_pooled_number_hides():
    """Both readers use scope_request; the pooled figure says nothing about whether they use
    it on the same events, which is the only question that matters for the rare class."""
    result = score(_published("round1"), _published("round2"))

    assert set(result.per_category) == {"included", "billable_extra", "scope_request", "noise"}
    assert result.per_category["noise"] > result.per_category["billable_extra"]


def test_the_confusion_table_renders_square():
    result = score(_published("round1"), _published("round2"))
    rendered = result.confusion_table().splitlines()

    header, rule, *rows = rendered
    assert len(rows) == len(result.marginals)
    assert header.count("|") == rule.count("|") == rows[0].count("|")


def test_alpha_generalises_to_a_panel_without_changing_the_two_rater_answer():
    """The two-rater form has to stay the special case, or every published figure moves."""
    from unlogged.eval.agreement import alpha_over_units, krippendorff_alpha

    pairs = [("A", "A")] * 20 + [("A", "B")] * 5 + [("B", "A")] * 10 + [("B", "B")] * 15

    assert round(krippendorff_alpha(pairs), 4) == 0.40
    assert round(alpha_over_units([[a, b] for a, b in pairs]), 4) == 0.40


def test_alpha_over_a_four_reader_panel():
    from unlogged.eval.agreement import alpha_over_units

    assert alpha_over_units([["A"] * 4, ["B"] * 4]) == 1.0
    # One dissenter in four costs real agreement but is not chance.
    assert 0.4 < alpha_over_units([["A", "A", "A", "B"], ["B", "B", "B", "B"]]) < 0.7


def test_a_unit_only_one_reader_saw_carries_no_agreement_and_is_dropped():
    """Alpha's own convention, and the reason it is the right coefficient for a panel where
    not everyone reads everything."""
    from unlogged.eval.agreement import alpha_over_units

    assert alpha_over_units([["A", "A"], ["B"]]) == alpha_over_units([["A", "A"]])


# -- the blind panel ------------------------------------------------------------------------


def _panel():
    from unlogged.eval.agreement import panel

    return panel({n: _published(f"blind-{n}") for n in "abcd"}, model=_published("model"))


def test_four_blind_readers_reproduce_the_published_panel_figures():
    """The numbers quoted in docs/CORPUS.md and the README.

    These four saw one frozen instruction and nothing else: not each other, not the earlier
    passes, not any critique, not this repository. That is what makes their agreement a
    statement about the task rather than about a shared starting point.
    """
    result = _panel()

    assert result.n == 31
    assert len(result.readers) == 4
    assert round(result.alpha, 3) == 0.797
    assert result.unanimous == 25
    assert round(result.ceiling, 3) == 0.943
    assert round(result.model, 3) == 0.613


def test_the_model_sits_well_below_a_ceiling_that_was_measured_not_assumed():
    """The comparison that matters: not "is the model right", which needs a truth nobody has,
    but "does the model agree with a panel as well as a member of that panel does"."""
    result = _panel()

    assert result.ceiling - result.model > 0.3


def test_the_clean_protocol_beats_the_contaminated_one_it_replaced():
    """The first attempt compared a pass with its own informed revision and reached 0.721.
    Four readers who had seen nothing reach 0.797 — so the contaminated figure understated the
    task rather than flattering it, which is the opposite of the usual direction and worth
    stating."""
    contaminated = score(_published("round1"), _published("round2")).alpha

    assert _panel().alpha > contaminated


def test_every_blind_reader_labelled_every_event():
    """A reader who skips the hard events makes agreement look better than it is, so the
    guideline requires a call on all of them and this checks it was given."""
    for n in "abcd":
        assert len(_published(f"blind-{n}")) == 31


def test_the_panel_disagreements_concentrate_on_one_reader_and_one_boundary():
    """Five of the six splits are one reader calling included or noise where the other three
    see work, or a request for work, outside the task list — the model's failure in milder
    form, from a reader who could not see the model."""
    readers = {n: _published(f"blind-{n}") for n in "abcd"}
    events = sorted(readers["a"])

    split = [e for e in events if len({readers[n][e] for n in "abcd"}) > 1]
    assert len(split) == 6

    lone_dissenter = [
        e
        for e in split
        if len({readers[n][e] for n in "bcd"}) == 1 and readers["a"][e] != readers["b"][e]
    ]
    assert len(lone_dissenter) == 4
    # And always in the same direction.
    assert {readers["a"][e] for e in lone_dissenter} <= {"included", "noise"}

    import collections

    calls = collections.Counter(readers["a"].values())
    assert calls["scope_request"] == 0 and calls["billable_extra"] == 0


def test_the_panel_uses_every_event_two_readers_saw_not_only_the_common_subset():
    """Intersecting down to the events everyone labelled is exactly what alpha exists to
    avoid: a panel where not everyone reads everything is the normal shape of an annotation
    effort, and discarding the ragged part reports a coefficient over data the reader was
    never told about. It changes nothing for the published figures, because all four readers
    labelled all 31 events — which is why it needed a test of its own.
    """
    from unlogged.eval.agreement import panel

    ragged = {
        "a": {"e1": "X", "e2": "Y", "e3": "X"},
        "b": {"e1": "X", "e2": "Y"},
        "c": {"e1": "X", "e3": "X"},
    }

    result = panel(ragged)

    assert result.n == 3, "the intersection is one event; the panel saw three"
    assert result.alpha == 1.0
    assert result.unanimous == 3


def test_an_event_only_one_reader_saw_is_left_out_of_the_panel():
    from unlogged.eval.agreement import panel

    result = panel({"a": {"e1": "X", "lonely": "Y"}, "b": {"e1": "X"}})

    assert result.n == 1


def test_the_published_panel_figures_are_unchanged_by_the_ragged_rule():
    """Pinned because the fix is invisible on this data and a later change to it would not be."""
    result = _panel()

    assert result.n == 31
    assert round(result.alpha, 3) == 0.797
    assert round(result.ceiling, 3) == 0.943
    assert round(result.model, 3) == 0.613
