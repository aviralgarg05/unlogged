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


def is_simulated(payload: dict[str, Any], *, sandbox: bool) -> bool:
    """Whether to treat this as a sandbox simulator event rather than a forgery.

    The simulator's events cannot be postback-verified, so a demo has to accept them on
    their id alone. That is a hole with a label on it: anyone who knows the URL can post
    `{"id": "WH-TEST-x", "event_type": "INVOICING.INVOICE.PAID"}` and be believed.

    Which is tolerable in a sandbox and is not tolerable anywhere else, so `sandbox` is a
    required keyword rather than a default. On a live account an event wearing a simulator's
    id is not a simulator event; it is someone trying the obvious thing.
    """
    if not sandbox:
        return False
    event_id = str(payload.get("id", ""))
    return event_id == "WH-SIMULATED" or event_id.startswith("WH-TEST")
