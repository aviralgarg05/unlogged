"""Webhook verification and the events this project listens for.

Signature verification is done PayPal's way — POST the received headers and the RAW body
back to /v1/notifications/verify-webhook-signature — rather than by reimplementing the
crypto. The raw bytes matter: re-serialising the parsed JSON changes the payload and the
verification fails for reasons that look like a signing bug.

The sandbox simulator (POST /v1/notifications/simulate-event) sends events that cannot be
postback-verified, so simulated traffic is accepted in sandbox and marked as simulated
rather than silently treated as genuine.
"""

from __future__ import annotations

from typing import Any

import structlog

from unlogged.paypal.client import PayPalClient

log = structlog.get_logger(__name__)

# The events that mean something to an engagement's bill.
SUBSCRIBED = [
    "INVOICING.INVOICE.PAID",
    "INVOICING.INVOICE.UPDATED",
    "INVOICING.INVOICE.CANCELLED",
    "PAYMENT.CAPTURE.COMPLETED",
]

REQUIRED_HEADERS = (
    "paypal-auth-algo",
    "paypal-cert-url",
    "paypal-transmission-id",
    "paypal-transmission-sig",
    "paypal-transmission-time",
)


class Webhooks:
    def __init__(self, client: PayPalClient):
        self.c = client

    def create(self, url: str, events: list[str] | None = None) -> dict[str, Any]:
        return self.c.request(
            "POST",
            "/v1/notifications/webhooks",
            json_body={
                "url": url,
                "event_types": [{"name": n} for n in (events or SUBSCRIBED)],
            },
        )

    def list(self) -> dict[str, Any]:
        return self.c.request("GET", "/v1/notifications/webhooks")

    def event_types(self) -> dict[str, Any]:
        return self.c.request("GET", "/v1/notifications/webhooks-event-types")

    def simulate(self, webhook_id: str, event_type: str) -> dict[str, Any]:
        """Drive an event deterministically, so a demo never waits on a sandbox buyer."""
        return self.c.request(
            "POST",
            "/v1/notifications/simulate-event",
            json_body={"webhook_id": webhook_id, "event_type": event_type},
        )

    def verify(self, headers: dict[str, str], raw_body: bytes, webhook_id: str) -> bool:
        """True only if PayPal confirms the signature over these exact bytes."""
        lower = {k.lower(): v for k, v in headers.items()}
        if any(h not in lower for h in REQUIRED_HEADERS):
            log.warning("webhook.missing_headers", have=sorted(lower))
            return False

        import json as _json

        body = {
            "auth_algo": lower["paypal-auth-algo"],
            "cert_url": lower["paypal-cert-url"],
            "transmission_id": lower["paypal-transmission-id"],
            "transmission_sig": lower["paypal-transmission-sig"],
            "transmission_time": lower["paypal-transmission-time"],
            "webhook_id": webhook_id,
            "webhook_event": _json.loads(raw_body),
        }
        resp = self.c.request("POST", "/v1/notifications/verify-webhook-signature", json_body=body)
        ok = resp.get("verification_status") == "SUCCESS"
        if not ok:
            log.warning("webhook.verification_failed", status=resp.get("verification_status"))
        return ok


def is_simulated(payload: dict[str, Any]) -> bool:
    """Simulator events carry the literal id and cannot be postback-verified."""
    return payload.get("id") == "WH-SIMULATED" or str(payload.get("id", "")).startswith("WH-TEST")
