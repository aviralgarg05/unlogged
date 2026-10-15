from decimal import Decimal

import pytest

from unlogged.paypal.invoices import COMPUTED, READONLY, LineItem, total_of


def test_line_item_totals_to_the_cent():
    li = LineItem(name="x", quantity=Decimal("1.5"), unit_price=Decimal("85.00"))
    assert li.total == Decimal("127.50")


def test_provenance_rides_in_the_name_so_the_payer_sees_it():
    li = LineItem(
        name="Retry logic on checkout",
        quantity=Decimal("2"),
        unit_price=Decimal("85.00"),
        provenance="slack 14 Oct",
    )
    assert li.display_name == "Retry logic on checkout (slack 14 Oct)"
    assert li.to_paypal()["name"] == li.display_name


def test_paypal_payload_shape():
    li = LineItem(name="x", quantity=Decimal("2"), unit_price=Decimal("65.00"), currency="GBP")
    p = li.to_paypal()
    assert p["unit_amount"] == {"currency_code": "GBP", "value": "65.00"}
    assert p["quantity"] == "2"


@pytest.mark.parametrize("field", ["id", "parent_id", "links"])
def test_readonly_set_matches_the_published_schema(field):
    # Exactly three top-level invoice properties carry readOnly. status, due_amount and
    # gratuity do NOT, contrary to folklore — see docs/VERIFIED.md.
    assert field in READONLY


@pytest.mark.parametrize("field", ["status", "due_amount", "effective_due_amount"])
def test_computed_fields_are_stripped_not_echoed(field):
    assert field in COMPUTED
    assert field not in READONLY


def test_total_of_reads_the_amount_value():
    assert total_of({"amount": {"value": "817.50"}}) == Decimal("817.50")
    assert total_of({}) == Decimal("0")
