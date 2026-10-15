import json
from decimal import Decimal
from pathlib import Path

from unlogged.scope.baseline import KeywordBaseline
from unlogged.scope.models import Call, Engagement, WorkEvent

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def engagement() -> Engagement:
    return Engagement.model_validate_json((FIX / "engagement.json").read_text())


def events() -> list[WorkEvent]:
    return [
        WorkEvent.model_validate_json(l)
        for l in (FIX / "events.jsonl").read_text().splitlines()
        if l.strip()
    ]


def test_engagement_parses_with_prose_clauses_and_a_rate_card():
    e = engagement()
    assert e.cap == Decimal("1200.00")
    assert e.rate_card.rate_for("design") == Decimal("65.00")
    assert e.rate_card.rate_for(None) == Decimal("85.00")
    assert e.clause("X1").kind == "exclusion"


def test_payer_note_states_the_scope_and_the_cap():
    note = engagement().payer_note()
    assert "Agreed cap USD 1,200.00" in note
    assert "checkout page" in note


def test_baseline_fires_on_polite_phrasing_and_misses_silent_work():
    """The two failure modes the model has to beat, pinned as tests rather than asserted."""
    evs = {e.id: e for e in events()}
    verdicts = {v.event_id: v for v in KeywordBaseline(engagement()).adjudicate(events())}

    # e4 is an administrative ask with no work in it — "could you also send me last
    # month's invoice" — and the baseline bills it anyway because it reads the phrasing.
    assert "could you also" in evs["e4"].text.lower()
    assert verdicts["e4"].call is Call.BILLABLE_EXTRA

    # e3 and e8 are real out-of-scope engineering that arrived with no request at all.
    assert verdicts["e3"].call is Call.NOISE
    assert verdicts["e8"].call is Call.NOISE


def test_every_event_gets_exactly_one_verdict():
    evs = events()
    verdicts = KeywordBaseline(engagement()).adjudicate(evs)
    assert len(verdicts) == len(evs)
    assert {v.event_id for v in verdicts} == {e.id for e in evs}


def test_provenance_is_human_readable():
    e = next(e for e in events() if e.id == "e3")
    assert e.provenance == "github 03 Oct"
