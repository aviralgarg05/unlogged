"""The money path, tested without a network.

`add_items` is the only call in this project that changes what a client owes, and every bug in
it is expensive in a specific way: a dropped item under-bills, a duplicated item over-bills, and
echoing back a server-computed field makes PayPal reject the write with an error that looks
nothing like its cause. These pin all three.
"""

from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from unlogged.paypal.invoices import COMPUTED, READONLY, Invoices, LineItem


class FakeClient:
    """Records what would have been sent, and answers reads from a stored invoice."""

    def __init__(self, invoice: dict[str, Any]):
        self.invoice = invoice
        self.calls: list[dict[str, Any]] = []

        class _S:
            base_url = "https://api-m.sandbox.paypal.com"

        self.s = _S()

    def request(self, method, path, *, json_body=None, params=None, **kw) -> Any:
        self.calls.append(
            {"method": method, "path": path, "body": json_body, "params": params, **kw}
        )
        if method == "GET":
            return self.invoice
        # A PUT returns the invoice as the server would recompute it.
        self.invoice = {**self.invoice, "items": json_body["items"]}
        return self.invoice


def invoice(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": "INV2-TEST-0000-0000-0009",
        "parent_id": None,
        "links": [{"rel": "self"}],
        "status": "UNPAID",
        "due_amount": {"currency_code": "USD", "value": "520.00"},
        "effective_due_amount": {"currency_code": "USD", "value": "520.00"},
        "payments": {"transactions": []},
        "detail": {"currency_code": "USD", "reference": "eng-1"},
        "items": items
        if items is not None
        else [
            {
                "name": "Agreed scope",
                "quantity": "8",
                "unit_amount": {"currency_code": "USD", "value": "65.00"},
            }
        ],
        "amount": {"currency_code": "USD", "value": "520.00"},
    }


def item(name: str = "Retry logic", hours: str = "2") -> LineItem:
    return LineItem(
        name=name,
        quantity=Decimal(hours),
        unit_price=Decimal("85.00"),
        provenance="github 03 Oct",
    )


def put_body(client: FakeClient) -> dict[str, Any]:
    return next(c for c in client.calls if c["method"] == "PUT")["body"]


def test_existing_items_are_kept_and_the_new_one_appended():
    c = FakeClient(invoice())
    Invoices(c).add_items("INV2-TEST-0000-0000-0009", [item()])
    items = put_body(c)["items"]
    assert len(items) == 2
    assert items[0]["name"] == "Agreed scope"
    assert items[1]["name"] == "Retry logic (github 03 Oct)"


@pytest.mark.parametrize("field", READONLY + COMPUTED)
def test_readonly_and_computed_fields_never_reach_the_wire(field):
    """Echoing any of these back is how a PUT fails with an error about something else."""
    c = FakeClient(invoice())
    Invoices(c).add_items("INV2-TEST-0000-0000-0009", [item()])
    assert field not in put_body(c)


def test_amount_is_reduced_to_its_currency_so_paypal_recomputes_the_total():
    # Sending back the amount.value we just read produces 400 calculation_error.
    c = FakeClient(invoice())
    Invoices(c).add_items("INV2-TEST-0000-0000-0009", [item()])
    assert put_body(c)["amount"] == {"currency_code": "USD"}


def test_notify_true_asks_paypal_to_tell_the_client_it_changed():
    c = FakeClient(invoice())
    Invoices(c).add_items("INV2-TEST-0000-0000-0009", [item()], notify=True)
    params = next(x for x in c.calls if x["method"] == "PUT")["params"]
    assert params == {"send_to_recipient": "true", "send_to_invoicer": "false"}


def test_a_retry_after_a_lost_response_does_not_bill_the_work_twice():
    """The failure this product cannot have.

    PayPal applied the write; the response never arrived; the caller retries. Because the
    client re-reads the invoice first, a key derived from the RESULTING document would differ
    on the second attempt and the duplicate would be accepted. Keyed on what is being added,
    it does not.
    """
    c = FakeClient(invoice())
    inv = Invoices(c)
    inv.add_items("INV2-TEST-0000-0000-0009", [item()])
    first_key = next(x for x in c.calls if x["method"] == "PUT")["idempotency"]

    # Same client, so the invoice now carries the line PayPal already applied.
    inv.add_items("INV2-TEST-0000-0000-0009", [item()])
    retry_key = [x for x in c.calls if x["method"] == "PUT"][-1]["idempotency"]

    assert retry_key == first_key, "a retry must reuse the key, or PayPal accepts a duplicate"


def test_a_different_addition_gets_a_different_key():
    a = FakeClient(invoice())
    Invoices(a).add_items("INV2-TEST-0000-0000-0009", [item()])
    b = FakeClient(invoice())
    Invoices(b).add_items("INV2-TEST-0000-0000-0009", [item(name="Something else")])
    key = lambda c: next(x for x in c.calls if x["method"] == "PUT")["idempotency"]  # noqa: E731
    assert key(a) != key(b)


def test_callers_may_key_on_the_originating_events():
    """Line text can be reworded; the events it came from cannot."""
    c = FakeClient(invoice())
    Invoices(c).add_items("INV2-TEST-0000-0000-0009", [item()], idempotency_key="e3,e8")
    assert next(x for x in c.calls if x["method"] == "PUT")["idempotency"].endswith("e3,e8")


@settings(max_examples=40, deadline=None)
@given(
    names=st.lists(
        st.text(min_size=1, max_size=30).filter(lambda s: s.strip()),
        min_size=1,
        max_size=6,
        unique=True,
    )
)
def test_appending_never_loses_an_item(names: list[str]):
    """However many are added, every one that was there is still there afterwards."""
    c = FakeClient(invoice())
    Invoices(c).add_items("INV2-TEST-0000-0000-0009", [item(name=n) for n in names])
    sent = [i["name"] for i in put_body(c)["items"]]
    assert sent[0] == "Agreed scope"
    assert len(sent) == len(names) + 1


# -- the cap, measured against the document that is written ---------------------------------


class GrowingClient(FakeClient):
    """A client whose invoice gains a line between one read and the next.

    Not a contrivance. Between a caller's read and the write, the invoice can gain a line from
    the other writer in a double-click, from the CLI running beside the service, or from a hand
    edit in PayPal's own dashboard. The whole reason this project has a reconcile command is
    that PayPal gives no ETag and accepts no If-Match, so this window cannot be closed — only
    measured at the right moment.
    """

    def __init__(self, before: dict[str, Any], after: dict[str, Any]):
        super().__init__(before)
        self.after = after
        self.reads = 0

    def request(self, method, path, *, json_body=None, params=None, **kw) -> Any:
        if method == "GET":
            self.reads += 1
            if self.reads > 1:
                self.invoice = self.after
        return super().request(method, path, json_body=json_body, params=params, **kw)


def test_the_cap_is_measured_against_the_invoice_being_written_not_an_earlier_read():
    """docs/HONESTY.md makes the cap the arithmetic bound on the case grounding cannot bound.

    A bound computed from a read the caller took before it decided to write is not a bound.
    Here the sequence is the real one: the caller reads (under the ceiling and happy to
    proceed), the invoice gains a line from somewhere else, and the document `add_items`
    actually PUTs is over. The cap is printed on the client's own page as a commitment.
    """
    from unlogged.paypal.invoices import Refused, total_of

    under = {**invoice(), "amount": {"currency_code": "USD", "value": "520.00"}}
    over = {**invoice(), "amount": {"currency_code": "USD", "value": "945.00"}}
    c = GrowingClient(under, over)
    inv = Invoices(c)
    cap = Decimal("1200.00")
    adding = [LineItem("Discovered work", Decimal("4"), Decimal("85.00"))]

    # What the caller sees, and decides on: 520 + 340 = 860, comfortably inside the cap.
    seen_by_caller = inv.get("INV2-TEST-0000-0000-0009")
    assert total_of(seen_by_caller) + Decimal("340.00") < cap

    # What is written: 945 + 340 = 1285, past a ceiling the client was told would hold.
    with pytest.raises(Refused, match="exceed the agreed cap"):
        inv.add_items("INV2-TEST-0000-0000-0009", adding, cap=cap)

    assert not [call for call in c.calls if call["method"] == "PUT"], "it wrote anyway"


def test_a_cap_that_is_not_reached_does_not_refuse():
    c = FakeClient(invoice())
    Invoices(c).add_items(
        "INV2-TEST-0000-0000-0009",
        [LineItem("Discovered work", Decimal("1"), Decimal("85.00"))],
        cap=Decimal("1200.00"),
    )
    assert [call for call in c.calls if call["method"] == "PUT"]


def test_a_refusal_is_a_value_error_so_existing_handlers_still_catch_it():
    """`Refused` narrows ValueError rather than replacing it — the apply path needs to tell
    "nothing was sent" from "something went wrong", and everything else should not care."""
    from unlogged.paypal.invoices import Refused

    assert issubclass(Refused, ValueError)
