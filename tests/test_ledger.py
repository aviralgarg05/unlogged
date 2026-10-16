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


def test_taking_the_lock_does_not_blank_the_page(tmp_path):
    """Opening the ledger in order to lock it created an empty file, which `_source` then
    preferred over the seed — so taking the lock was enough to blank the page titled "Every
    line this system added to the live PayPal invoice", on a fresh clone, before anything had
    been billed.
    """
    from decimal import Decimal

    from unlogged.ledger import Entry, Ledger, now

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    seeded = Entry(
        at=now(),
        invoice_id="INV2-TEST-0000-0000-0005",
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
    with ledger.guard():
        pass

    assert [e.event_id for e in ledger] == ["p1"]


def test_an_empty_local_file_is_not_local_history(tmp_path):
    """It is what a crashed first run leaves behind, and preferring it over the seed makes the
    product's own summary render blank for a reason nobody can see."""
    from decimal import Decimal

    from unlogged.ledger import Entry, Ledger, now

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "eng.jsonl").write_text(
        Entry(
            at=now(),
            invoice_id="INV2-TEST-0000-0000-0005",
            event_id="p1",
            clause_id="X1",
            line_name="Earlier period",
            hours=Decimal("1"),
            unit_price=Decimal("85.00"),
            total_after=Decimal("85.00"),
            adjudicator="gpt-6.1-sol",
            confidence=0.9,
        ).line()
        + "\n"
    )
    (tmp_path / "eng.jsonl").write_text("")

    assert [e.event_id for e in Ledger(tmp_path / "eng.jsonl")] == ["p1"]


def test_the_money_total_counts_one_row_per_billed_line(tmp_path):
    """The file holds up to three rows per line — the intent before the money moves, the
    settled row after, and a void where the write never left. Those exist so a write cannot
    be lost or repeated, and summing them as money made $382.50 of real work report as
    $1,105.00, while an apply that billed nothing still moved the total.
    """
    import json
    from decimal import Decimal

    from unlogged.ledger import Entry, Ledger, now

    ledger = Ledger(tmp_path / "eng.jsonl")

    def row(event_id, **kw):
        return Entry(
            at=now(),
            invoice_id="INV2-TEST-0000-0000-0009",
            event_id=event_id,
            clause_id="X1",
            line_name=f"Work for {event_id}",
            hours=Decimal("2"),
            unit_price=Decimal("85.00"),
            total_after=Decimal("0"),
            adjudicator="gpt-6.1-sol",
            confidence=0.9,
            **kw,
        )

    # One line, billed properly: intent then settled.
    ledger.append(row("e3", settled=False))
    ledger.append(row("e3"))
    assert ledger.total_added() == Decimal("170.00")
    assert ledger.summary()["changes"] == 1

    # A second line attempted and voided bills nothing and counts as nothing.
    ledger.append(row("e8", settled=False))
    ledger.append(row("e8", settled=False, voided=True))
    assert ledger.total_added() == Decimal("170.00")
    assert ledger.summary()["changes"] == 1

    # And when it is billed for real afterwards, it counts once.
    ledger.append(row("e8", settled=False))
    ledger.append(row("e8"))
    assert ledger.total_added() == Decimal("340.00")
    assert ledger.summary()["changes"] == 2

    # The raw file still holds every row: the bookkeeping is kept, it is just not money.
    assert len((tmp_path / "eng.jsonl").read_text().strip().splitlines()) == 6
    assert all(json.loads(line) for line in (tmp_path / "eng.jsonl").read_text().splitlines())


def test_the_api_returns_one_row_per_line_so_the_chart_cannot_draw_bookkeeping(
    tmp_path, monkeypatch
):
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from unlogged import web as web_mod
    from unlogged.ledger import Entry, Ledger, now

    monkeypatch.setattr(web_mod, "DATA", tmp_path)
    ledger = Ledger(tmp_path / "eng-checkout-001.jsonl")
    for settled in (False, True):
        ledger.append(
            Entry(
                at=now(),
                invoice_id="INV2-TEST-0000-0000-0009",
                event_id="e3",
                clause_id="X1",
                line_name="One line",
                hours=Decimal("2"),
                unit_price=Decimal("85.00"),
                total_after=Decimal("170.00"),
                adjudicator="gpt-6.1-sol",
                confidence=0.9,
                settled=settled,
            )
        )

    body = TestClient(web_mod.app).get("/api/ledger").json()

    assert len(body["rows"]) == 1, "the chart would otherwise draw the intent row as a bar"
    assert body["summary"]["added"] == "170.00"


def test_a_zero_byte_ledger_does_not_erase_the_seeded_history(tmp_path):
    """`_source` treated an empty file as absent and read the seed; `append` treated it as
    present and did not carry the seed forward. So one append to an empty file erased the
    engagement's history — from an append-only record.
    """
    from decimal import Decimal

    from unlogged.ledger import Entry, Ledger, now

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "eng.jsonl").write_text(
        Entry(
            at=now(),
            invoice_id="INV2-TEST-0000-0000-0010",
            event_id="p1",
            clause_id="X1",
            line_name="Earlier period",
            hours=Decimal("1"),
            unit_price=Decimal("85.00"),
            total_after=Decimal("85.00"),
            adjudicator="gpt-6.1-sol",
            confidence=0.9,
        ).line()
        + "\n"
    )
    (tmp_path / "eng.jsonl").write_text("")

    ledger = Ledger(tmp_path / "eng.jsonl")
    ledger.append(
        Entry(
            at=now(),
            invoice_id="INV2-TEST-0000-0000-0011",
            event_id="e3",
            clause_id="X1",
            line_name="New work",
            hours=Decimal("1"),
            unit_price=Decimal("85.00"),
            total_after=Decimal("85.00"),
            adjudicator="gpt-6.1-sol",
            confidence=0.9,
        )
    )

    assert [e.event_id for e in ledger] == ["p1", "e3"]


def test_the_service_and_the_cli_lock_the_same_file(monkeypatch, tmp_path):
    """The cross-process lock is the whole point, and the service hardcoded `data` while the
    CLI honoured UNLOGGED_DATA — so whenever it was set, which is every test run and every
    scripted demo, the two locked different files and guarded nothing across each other."""
    import importlib

    monkeypatch.setenv("UNLOGGED_DATA", str(tmp_path))
    from unlogged import cli, web

    importlib.reload(cli)
    importlib.reload(web)
    try:
        assert cli.DATA.resolve() == web.DATA.resolve() == tmp_path.resolve()
    finally:
        monkeypatch.delenv("UNLOGGED_DATA", raising=False)
        importlib.reload(cli)
        importlib.reload(web)
