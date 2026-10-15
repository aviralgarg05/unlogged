"""What actually landed, via the APIMatic-generated PayPal Server SDK.

The contractor's question does not end at "the client paid". For cross-border work it ends at
"how much reached me", and the gap between the two is PayPal's cross-border and conversion cut.
`seller_receivable_breakdown` on a capture is where PayPal states that itself: gross, fee, net,
and the exchange rate it used.

This is the one part of the product the APIMatic SDK can serve, and it is used deliberately
rather than decoratively. **The SDK ships six controllers — oauth, orders, payments,
subscriptions, transaction search, vault — and none of them is Invoicing.** Everything this
product does to an invoice therefore has to go through `paypal/invoices.py` on httpx. That gap
is reported in `docs/UPSTREAM.md` rather than worked around quietly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import structlog

from unlogged.config import Settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Settlement:
    """PayPal's own arithmetic on one capture. Every figure here is PayPal's, not ours."""

    capture_id: str
    gross: Decimal
    fee: Decimal
    net: Decimal
    currency: str
    exchange_rate: str | None
    received_currency: str | None

    @property
    def fee_fraction(self) -> Decimal:
        return (self.fee / self.gross).quantize(Decimal("0.0001")) if self.gross else Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "gross": str(self.gross),
            "fee": str(self.fee),
            "net": str(self.net),
            "currency": self.currency,
            "exchange_rate": self.exchange_rate,
            "received_currency": self.received_currency,
            "fee_fraction": str(self.fee_fraction),
        }


def _money(obj: Any) -> tuple[Decimal, str]:
    if obj is None:
        return Decimal("0"), ""
    value = getattr(obj, "value", None) or (obj.get("value") if isinstance(obj, dict) else None)
    code = getattr(obj, "currency_code", None) or (
        obj.get("currency_code") if isinstance(obj, dict) else None
    )
    return Decimal(str(value or "0")), str(code or "")


def read_settlement(settings: Settings, capture_id: str) -> Settlement | None:
    """Read one capture's breakdown. Returns None when PayPal does not supply one.

    Not every capture carries a `seller_receivable_breakdown` — a same-currency capture may
    report only the net. Returning None says so rather than inventing zeroes.
    """
    from paypalserversdk.configuration import Environment
    from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
    from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient

    client = PaypalServersdkClient(
        environment=(
            Environment.SANDBOX if "sandbox" in settings.base_url else Environment.PRODUCTION
        ),
        client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
            o_auth_client_id=settings.client_id,
            o_auth_client_secret=settings.client_secret,
        ),
    )
    # The SDK returns an ApiResponse envelope; the payload is on .body.
    response = client.payments.get_captured_payment({"capture_id": capture_id})
    capture = getattr(response, "body", None)
    if capture is None:
        return None

    breakdown = getattr(capture, "seller_receivable_breakdown", None)
    if breakdown is None:
        log.info("settlement.no_breakdown", capture_id=capture_id)
        return None

    gross, currency = _money(getattr(breakdown, "gross_amount", None))
    fee, _ = _money(getattr(breakdown, "paypal_fee", None))
    net, _ = _money(getattr(breakdown, "net_amount", None))
    received = getattr(breakdown, "receivable_amount", None)
    _, received_currency = _money(received) if received is not None else (Decimal("0"), None)

    return Settlement(
        capture_id=capture_id,
        gross=gross,
        fee=fee,
        net=net,
        currency=currency,
        exchange_rate=getattr(breakdown, "exchange_rate", None)
        and str(getattr(getattr(breakdown, "exchange_rate", None), "value", "") or ""),
        received_currency=received_currency or None,
    )
