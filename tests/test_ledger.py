import json
from decimal import Decimal
from pathlib import Path

from unlogged.ledger import Entry, Ledger, now


def entry(**kw) -> Entry:
    base = {
        "at": now(),
        "invoice_id": "INV2-TEST-0000-0000-0009",
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


def test_a_fresh_clone_reads_the_seeded_ledger(tmp_path: Path):
    """The climax page must not be blank on the documented judge path."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "eng.jsonl").write_text(entry().line() + "\n")

    led = Ledger(tmp_path / "eng.jsonl")
    assert [e.event_id for e in led] == ["e1"]

    # The seed is carried into the local file on the first write, so the history continues
    # rather than restarting. See test_the_seed_survives_the_first_local_write below.
    led.append(entry(event_id="e9"))
    assert [e.event_id for e in led] == ["e1", "e9"]


def test_the_seed_survives_the_first_local_write(tmp_path):
    """The seed was read only when no local file existed, so earlier periods disappeared as
    soon as one line was billed — from a record whose whole purpose is not to forget a step.
    """
    from decimal import Decimal

    from unlogged.ledger import Entry, Ledger, now

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    seeded = Entry(
        at=now(),
        invoice_id="INV2-TEST-0000-0000-0003",
        event_id="p1",
        clause_id="X1",
        line_name="Earlier period",
        hours=Decimal("1"),
        unit_price=Decimal("85.00"),
        total_after=Decimal("85.00"),
        adjudicator="gpt-6.1-sol",
        confidence=0.9,
    )
    (seed_dir / "eng.jsonl").write_text(seeded.line() + "\n")

    ledger = Ledger(tmp_path / "eng.jsonl")
    assert [e.event_id for e in ledger] == ["p1"]

    ledger.append(
        seeded.model_copy(update={"event_id": "e3", "invoice_id": "INV2-TEST-0000-0000-0004"})
    )

    assert [e.event_id for e in ledger] == ["p1", "e3"]


def test_a_row_records_what_it_added_not_just_the_rate():
    """The dashboard summed `unit_price` for "Added after sending" and for the chart titled
    "What each discovered line added to the bill", so both reported the hourly rate: four
    identical bars at $85 and a total that matched no invoice.
    """
    from decimal import Decimal

    from unlogged.ledger import Entry, now

    e = Entry(
        at=now(),
        invoice_id="INV2-TEST-0000-0000-0001",
        event_id="e3",
        clause_id="X1",
        line_name="PSP timeout handling",
        hours=Decimal("3"),
        unit_price=Decimal("85.00"),
        total_after=Decimal("902.50"),
        adjudicator="gpt-6.1-sol",
        confidence=0.9,
    )
    assert e.line_total == Decimal("255.00")
    # Derived, so a stored row can never disagree with the arithmetic.
    assert json.loads(e.line())["line_total"] == "255.00"


def test_half_hours_do_not_lose_a_cent():
    from decimal import Decimal

    from unlogged.ledger import Entry, now

    e = Entry(
        at=now(),
        invoice_id="INV2-TEST-0000-0000-0001",
        event_id="e8",
        clause_id="X1",
        line_name="Idempotency keys",
        hours=Decimal("1.5"),
        unit_price=Decimal("85.00"),
        total_after=Decimal("902.50"),
        adjudicator="gpt-6.1-sol",
        confidence=0.9,
    )
    assert e.line_total == Decimal("127.50")
