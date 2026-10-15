from decimal import Decimal
from pathlib import Path

from unlogged.ledger import Entry, Ledger, now


def entry(**kw) -> Entry:
    base = {
        "at": now(),
        "invoice_id": "INV2-TEST",
        "event_id": "e1",
        "clause_id": "X1",
        "line_name": "Retry logic (slack 02 Oct)",
        "hours": Decimal(2),
        "unit_price": Decimal("85.00"),
        "total_after": Decimal("690.00"),
        "adjudicator": "keyword-baseline",
        "confidence": 0.5,
    }
    return Entry(**{**base, **kw})


def test_ledger_is_append_only_and_round_trips(tmp_path: Path):
    led = Ledger(tmp_path / "eng.jsonl")
    led.append(entry())
    led.append(entry(event_id="e3", hours=Decimal("1.5"), total_after=Decimal("817.50")))
    rows = list(led)
    assert [r.event_id for r in rows] == ["e1", "e3"]
    assert led.total_added() == Decimal("297.50")


def test_summary_of_an_empty_ledger_does_not_explode(tmp_path: Path):
    s = Ledger(tmp_path / "none.jsonl").summary()
    assert s == {"changes": 0, "added": "0.00", "first": None, "last": None}
