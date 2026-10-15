from decimal import Decimal

from unlogged.paypal.settlement import Settlement, _money


def settlement(**kw) -> Settlement:
    base = {
        "capture_id": "CAP-1",
        "gross": Decimal("817.50"),
        "fee": Decimal("38.29"),
        "net": Decimal("779.21"),
        "currency": "USD",
        "exchange_rate": None,
        "received_currency": None,
    }
    return Settlement(**{**base, **kw})


def test_fee_fraction_is_what_the_contractor_actually_lost():
    s = settlement()
    assert s.fee_fraction == Decimal("0.0468")


def test_a_zero_gross_does_not_divide_by_zero():
    assert settlement(gross=Decimal("0"), fee=Decimal("0")).fee_fraction == Decimal("0")


def test_to_dict_keeps_money_as_strings():
    d = settlement().to_dict()
    assert d["gross"] == "817.50" and d["net"] == "779.21"
    assert isinstance(d["fee_fraction"], str)


def test_money_reads_both_sdk_objects_and_plain_dicts():
    """The SDK returns model objects; cassettes replay dicts. Both must parse."""

    class Money:
        value = "100.00"
        currency_code = "GBP"

    assert _money(Money()) == (Decimal("100.00"), "GBP")
    assert _money({"value": "12.34", "currency_code": "EUR"}) == (Decimal("12.34"), "EUR")
    assert _money(None) == (Decimal("0"), "")
