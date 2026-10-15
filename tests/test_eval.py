from decimal import Decimal
from pathlib import Path

from unlogged.eval.harness import Gold, report, score, write_junit
from unlogged.scope.baseline import KeywordBaseline
from unlogged.scope.models import Call, Engagement, WorkEvent

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def load():
    eng = Engagement.model_validate_json((FIX / "engagement.json").read_text())
    evs = [
        WorkEvent.model_validate_json(l)
        for l in (FIX / "events.jsonl").read_text().splitlines()
        if l.strip()
    ]
    gold = [
        Gold.model_validate_json(l)
        for l in (FIX / "gold.jsonl").read_text().splitlines()
        if l.strip()
    ]
    return eng, evs, gold


def test_gold_covers_every_event_exactly_once():
    _, evs, gold = load()
    assert [g.event_id for g in gold] == [e.id for e in evs]


def test_gold_separates_the_ask_from_the_work():
    """e1 asks for retry logic; e3 is the PR that does it. Billing both double-charges."""
    _, _, gold = load()
    by = {g.event_id: g for g in gold}
    assert by["e1"].call is Call.SCOPE_REQUEST
    assert by["e3"].call is Call.BILLABLE_EXTRA
    assert by["e3"].hours == Decimal("3.0")


def test_baseline_scores_zero_on_both_precision_and_recall():
    """The ablation arm, pinned. It bills a request and an admin message, and misses
    both pieces of real out-of-scope engineering."""
    eng, evs, gold = load()
    r = score(KeywordBaseline(eng), evs, gold, eng)
    assert r.precision == 0.0
    assert r.recall == 0.0
    assert set(r.overbilled) == {"e1", "e4"}
    assert set(r.missed) == {"e3", "e8"}
    assert r.money_overbilled == Decimal("170.00")
    assert r.money_missed == Decimal("425.00")


def test_report_names_both_error_classes_separately():
    eng, evs, gold = load()
    md = report([score(KeywordBaseline(eng), evs, gold, eng)], eng, gold)
    assert "overbilled" in md and "missed" in md
    # A single accuracy headline would hide the expensive error, so there must not be one.
    assert "| accuracy | precision | recall |" in md


def test_junit_marks_each_mistake_as_a_failing_case(tmp_path: Path):
    eng, evs, gold = load()
    write_junit([score(KeywordBaseline(eng), evs, gold, eng)], tmp_path / "junit.xml")
    xml = (tmp_path / "junit.xml").read_text()
    assert 'failures="4"' in xml
    assert "no_overbill_e1" in xml and "no_miss_e3" in xml
