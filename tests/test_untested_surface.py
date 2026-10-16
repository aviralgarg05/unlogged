"""Behaviour this project documents as verified and never tested.

An audit found each of these by mutating the code and watching the suite stay green: swap
gross and net in the settlement reader, point every sandbox link at live paypal.com, turn the
client's notification off on both write paths, revert the importer's pagination to the exact
bug that dropped 135 comments — and 178 tests had nothing to say about any of it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from unlogged import cassette
from unlogged.config import LIVE, SANDBOX, Settings
from unlogged.paypal import Invoices, LineItem, PayPalClient
from unlogged.paypal import invoices as inv_mod


def _client(base=SANDBOX):
    return PayPalClient(
        Settings(client_id="", client_secret="", base_url=base, openai_api_key=None, replay=True)
    )


# -- the link the client keeps ---------------------------------------------------------------


def test_a_sandbox_invoice_links_to_sandbox_and_a_live_one_does_not():
    """Pointing every sandbox link at live paypal.com survived the whole suite. The payer URL
    is the thing the client bookmarks on day one; the wrong host is a dead link for the life
    of the engagement."""
    with _client(SANDBOX) as c:
        sandbox_url = Invoices(c).payer_url("INV2-TEST-0000-0000-0008")
    with _client(LIVE) as c:
        live_url = Invoices(c).payer_url("INV2-TEST-0000-0000-0008")

    assert sandbox_url.startswith("https://www.sandbox.paypal.com/invoice/payerView/details/")
    assert live_url.startswith("https://www.paypal.com/invoice/payerView/details/")
    assert "sandbox" not in live_url
    # The QR flag is what makes the printed code and the link the same page.
    assert sandbox_url.endswith("?qr=1")


# -- the consent step ------------------------------------------------------------------------


def test_the_client_is_notified_when_a_line_is_added(tmp_path, monkeypatch):
    """`send_to_recipient` is the consent step: PayPal emails the client that their invoice
    changed. It could be switched off on both write paths with nothing failing, which would
    turn "the client is told" from a property into a comment.
    """
    sent: dict[str, str] = {}

    class Fake:
        def request(self, _m, _p, *, json_body=None, params=None, **_kw):
            if params:
                sent.update(params)
            return {"items": [], "amount": {"value": "0.00"}}

    inv = inv_mod.Invoices.__new__(inv_mod.Invoices)
    inv.c = Fake()
    inv.get = lambda _id, **_kw: {"items": [], "detail": {"currency_code": "USD"}}

    inv.add_items(
        "INV2-TEST-0000-0000-0008",
        [LineItem("Work", Decimal("1"), Decimal("85.00"))],
        notify=True,
    )

    assert sent["send_to_recipient"] == "true"
    assert sent["send_to_invoicer"] == "false"


def test_the_documented_apply_notifies_the_client(tmp_path, monkeypatch):
    """End to end on the path a contractor actually runs."""
    from pathlib import Path

    from typer.testing import CliRunner

    from unlogged import cli

    seen: dict[str, bool] = {}
    original = Invoices.add_items

    def spy(self, invoice_id, items, *, notify=True, idempotency_key=None):
        seen["notify"] = notify
        return original(self, invoice_id, items, notify=notify, idempotency_key=idempotency_key)

    monkeypatch.setattr(Invoices, "add_items", spy)
    monkeypatch.setattr(cli, "DATA", tmp_path)
    for var in ("OPENAI_API_KEY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("UNLOGGED_REPLAY", "1")

    root = Path(__file__).resolve().parents[1]
    result = CliRunner().invoke(
        cli.app,
        [
            "discover",
            "--engagement",
            str(root / "fixtures" / "engagement.json"),
            "--events",
            str(root / "fixtures" / "events.jsonl"),
            "--invoice-id",
            (root / "fixtures" / "demo-invoice-id").read_text().strip(),
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen["notify"] is True, "the client was not told their invoice changed"


# -- the rate card ---------------------------------------------------------------------------


def test_a_category_is_priced_from_its_own_rate_not_the_default():
    """Both write paths could bill the default rate for every category and nothing failed, so
    the rate card was decoration."""
    from unlogged.scope.models import RateCard

    card = RateCard(
        default_rate=Decimal("85.00"),
        by_category={"design": Decimal("65.00"), "discovery": Decimal("0.00")},
    )

    assert card.rate_for("design") == Decimal("65.00")
    assert card.rate_for("discovery") == Decimal("0.00"), "zero is a rate, not a missing one"
    assert card.rate_for("engineering") == Decimal("85.00")
    assert card.rate_for(None) == Decimal("85.00")


def test_the_demo_prices_design_and_engineering_differently():
    """The fixture's two billable extras are engineering at 85 and the opening is design at
    65. If every category collapsed to the default the demo total would still look plausible,
    which is why this is pinned."""
    import json
    from pathlib import Path

    from unlogged.scope.models import Engagement

    root = Path(__file__).resolve().parents[1]
    eng = Engagement.model_validate(json.loads((root / "fixtures" / "engagement.json").read_text()))

    assert eng.rate_card.rate_for("design") == Decimal("65.00")
    assert eng.rate_card.rate_for("engineering") == Decimal("85.00")
    assert eng.rate_card.rate_for("design") != eng.rate_card.rate_for("engineering")


# -- a rate that cannot be billed --------------------------------------------------------------


def test_a_rate_with_more_than_two_decimals_is_refused():
    """`unit_amount` goes out at two decimals, so 85.333 was sent as 85.33 while the line's own
    total kept the third: the ledger recorded 256.00 against three hours and the client paid
    255.99. A cent, each time, between the seller's record and the client's invoice."""
    with pytest.raises(ValueError, match="not a billable rate"):
        LineItem("Work", Decimal("3"), Decimal("85.333"))

    ok = LineItem("Work", Decimal("3"), Decimal("85.33"))
    assert ok.total == Decimal(ok.to_paypal()["unit_amount"]["value"]) * Decimal("3")


# -- the importer's pagination -----------------------------------------------------------------


def test_the_importer_reads_past_the_first_page(tmp_path):
    """It stopped after three pages and said nothing, so a repository with 435 issue comments
    yielded 300 and the 135 it dropped were the most recent. Reverting to that bug used to
    survive the suite."""
    from unlogged.sources.github import GitHub

    gh = GitHub("o/r", replay=True)
    gh.tape = cassette.Tape(tmp_path)

    def page(n, size):
        return [
            {
                "id": 1000 + n * 100 + i,
                "body": f"comment {n}-{i}",
                "created_at": "2026-10-03T00:00:00Z",
                "user": {"login": "human"},
            }
            for i in range(size)
        ]

    for n, size in ((1, 100), (2, 100), (3, 100), (4, 7)):
        gh.tape.record(
            cassette.key({"gh": "/repos/o/r/issues/comments", "q": {"per_page": 100, "page": n}}),
            {"status": 200, "body": page(n, size)},
        )
    for path, params in (
        ("/repos/o/r/pulls", {"state": "all"}),
        ("/repos/o/r/issues", {"state": "all"}),
        ("/repos/o/r/pulls/comments", {}),
    ):
        gh.tape.record(
            cassette.key({"gh": path, "q": {"per_page": 100, "page": 1, **params}}),
            {"status": 200, "body": []},
        )

    events = gh.events()

    assert len(events) == 307, "a page cap would make this 300 or fewer, silently"
    assert any(e.text.endswith("comment 4-6") for e in events), "the last page was dropped"


# -- the QR the client files on day one ---------------------------------------------------


def _multipart(png: bytes) -> bytes:
    import base64 as b64

    body = b64.b64encode(png)
    return (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="image"\r\n'
        b"Content-Type: text/plain\r\n\r\n" + body + b"\r\n--boundary--\r\n"
    )


def test_the_qr_is_decoded_out_of_paypals_multipart_envelope(tmp_path):
    """`generate-qr-code` answers multipart/form-data, not image/png: the PNG arrives as
    base64 text in a part whose own Content-Type is text/plain. That is upstream report four,
    and the decoding of it had no test — so a change that returned the envelope itself would
    have shipped a broken QR on the one artifact the client keeps."""
    png = b"\x89PNG\r\n\x1a\n" + b"pretend pixels"

    class Fake:
        def request(self, _m, _p, **_kw):
            return {
                "_raw_b64": _multipart(png).hex(),
                "_ct": "multipart/form-data; boundary=boundary",
            }

    inv = inv_mod.Invoices.__new__(inv_mod.Invoices)
    inv.c = Fake()

    out = inv.qr_png("INV2-TEST-0000-0000-0008")

    assert out == png
    assert out[:4] == b"\x89PNG", "whatever else changes, it has to be a PNG"


def test_a_plain_png_response_is_passed_through_unharmed():
    """If PayPal ever fixes the envelope, the decoder must not corrupt the fixed response."""
    png = b"\x89PNG\r\n\x1a\nstraight through"

    class Fake:
        def request(self, _m, _p, **_kw):
            return {"_raw_b64": png.hex(), "_ct": "image/png"}

    inv = inv_mod.Invoices.__new__(inv_mod.Invoices)
    inv.c = Fake()

    assert inv.qr_png("INV2-TEST-0000-0000-0008") == png


# -- what the seller actually receives ------------------------------------------------------


class _Money:
    def __init__(self, value, currency_code="USD"):
        self.value, self.currency_code = value, currency_code


class _Breakdown:
    def __init__(self, **kw):
        self.gross_amount = kw.get("gross")
        self.paypal_fee = kw.get("fee")
        self.net_amount = kw.get("net")
        self.receivable_amount = kw.get("received")
        self.exchange_rate = kw.get("rate")


def _capture(breakdown):
    envelope = type("Response", (), {})()
    envelope.body = type("Capture", (), {"seller_receivable_breakdown": breakdown})()
    return envelope


def _read(monkeypatch, breakdown):
    from unlogged.paypal import settlement as mod

    class FakeSdk:
        def __init__(self, **_kw):
            self.payments = type(
                "Payments", (), {"get_captured_payment": lambda _s, _a: _capture(breakdown)}
            )()

    monkeypatch.setitem(
        __import__("sys").modules,
        "paypalserversdk.paypal_serversdk_client",
        type("M", (), {"PaypalServersdkClient": FakeSdk}),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "paypalserversdk.configuration",
        type("M", (), {"Environment": type("E", (), {"SANDBOX": 1, "PRODUCTION": 2})}),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "paypalserversdk.http.auth.o_auth_2",
        type("M", (), {"ClientCredentialsAuthCredentials": lambda **_kw: None}),
    )
    return mod.read_settlement(
        Settings(
            client_id="i", client_secret="s", base_url=SANDBOX, openai_api_key=None, replay=False
        ),
        "CAP-1",
    )


def test_gross_fee_and_net_are_not_swapped(monkeypatch):
    """Swapping gross and net survived the whole suite. These are the three numbers a
    contractor checks against their bank, and PayPal supplies all of them."""
    result = _read(
        monkeypatch,
        _Breakdown(
            gross=_Money("902.50"),
            fee=_Money("26.47"),
            net=_Money("876.03"),
            received=_Money("876.03", "USD"),
        ),
    )

    assert result is not None
    assert result.gross == Decimal("902.50")
    assert result.fee == Decimal("26.47")
    assert result.net == Decimal("876.03")
    assert result.gross - result.fee == result.net, "PayPal's own arithmetic has to hold"
    assert result.currency == "USD"


def test_a_capture_with_no_breakdown_says_so_rather_than_inventing_zeroes(monkeypatch):
    """Not every capture carries one — a same-currency capture may report only the net — and
    zeroes would read as a free transaction."""
    assert _read(monkeypatch, None) is None


# -- money that arrived outside PayPal ------------------------------------------------------


def test_an_out_of_band_payment_is_posted_in_paypals_own_shape():
    """Verified live — a $100 bank transfer moved a $690 invoice to PARTIALLY_PAID with
    $590 due, and a later line left the payment intact — and then never tested. Contractors
    are paid by bank transfer constantly; without this the client pays and the invoice goes
    on asking."""
    sent: dict = {}

    class Fake:
        def request(self, method, path, *, json_body=None, **_kw):
            sent.update({"method": method, "path": path, "body": json_body})
            return {"payment_id": "PAY-1"}

    inv = inv_mod.Invoices.__new__(inv_mod.Invoices)
    inv.c = Fake()

    inv.record_payment(
        "INV2-TEST-0000-0000-0008",
        amount=Decimal("100.00"),
        when="2026-10-16",
        note="Bank transfer, reference NW-0042",
    )

    assert sent["method"] == "POST"
    assert sent["path"].endswith("/INV2-TEST-0000-0000-0008/payments")
    assert sent["body"]["method"] == "BANK_TRANSFER"
    assert sent["body"]["payment_date"] == "2026-10-16"
    # Two decimals, as a string: PayPal rejects a float and silently loses a third decimal.
    assert sent["body"]["amount"] == {"currency_code": "USD", "value": "100.00"}
    assert sent["body"]["note"] == "Bank transfer, reference NW-0042"


def test_a_payment_without_a_note_does_not_send_an_empty_one():
    sent: dict = {}

    class Fake:
        def request(self, _m, _p, *, json_body=None, **_kw):
            sent.update(json_body)
            return {}

    inv = inv_mod.Invoices.__new__(inv_mod.Invoices)
    inv.c = Fake()

    inv.record_payment("INV2-TEST-0000-0000-0008", amount=Decimal("40"), when="2026-10-16")

    assert "note" not in sent
    assert sent["amount"]["value"] == "40.00"
