"""Webhook verification, which had no tests at all.

This endpoint is the one unauthenticated door into the service. What arrives through it is a
stranger's JSON claiming that an invoice was paid.
"""

from __future__ import annotations

import json

from unlogged.config import LIVE, SANDBOX, Settings
from unlogged.paypal.webhooks import REQUIRED_HEADERS, Webhooks, is_simulated

GENUINE_HEADERS = dict.fromkeys(REQUIRED_HEADERS, "x")


def _settings(base=SANDBOX):
    return Settings(
        client_id="id", client_secret="secret", base_url=base, openai_api_key=None, replay=False
    )


class _Recording:
    """Stands in for PayPal's verify endpoint, and remembers what it was sent."""

    def __init__(self, status="SUCCESS"):
        self.status, self.sent = status, None

    def request(self, _method, _path, *, json_body, **_kw):
        self.sent = json_body
        return {"verification_status": self.status}


def _webhooks(fake):
    w = Webhooks.__new__(Webhooks)
    w.c = fake
    return w


def test_a_payload_paypal_does_not_confirm_is_refused():
    fake = _Recording("FAILURE")

    assert _webhooks(fake).verify(GENUINE_HEADERS, b"{}", "WH-ID") is False


def test_a_payload_paypal_confirms_is_accepted():
    assert _webhooks(_Recording("SUCCESS")).verify(GENUINE_HEADERS, b"{}", "WH-ID") is True


def test_every_required_header_is_required():
    """Dropping any one of the five must fail verification, not be filled in with a default."""
    for missing in REQUIRED_HEADERS:
        headers = {h: "x" for h in REQUIRED_HEADERS if h != missing}
        fake = _Recording("SUCCESS")

        assert _webhooks(fake).verify(headers, b"{}", "WH-ID") is False, missing
        assert fake.sent is None, f"{missing} absent and PayPal was still asked"


def test_headers_are_matched_without_regard_to_case():
    """A real server may send Paypal-Transmission-Id. Case-sensitivity here would reject
    genuine traffic and look like a signing bug."""
    shouted = {h.upper(): "x" for h in REQUIRED_HEADERS}

    assert _webhooks(_Recording("SUCCESS")).verify(shouted, b"{}", "WH-ID") is True


def test_verification_is_asked_about_the_bytes_that_arrived():
    """Re-serialising the parsed body changes it, and the signature is over what was sent."""
    raw = b'{"id":"WH-REAL","event_type":"INVOICING.INVOICE.PAID"}'
    fake = _Recording("SUCCESS")

    _webhooks(fake).verify(GENUINE_HEADERS, raw, "WH-ID")

    assert fake.sent["webhook_event"] == json.loads(raw)
    assert fake.sent["webhook_id"] == "WH-ID"
    # PayPal's own field names, which are the header names without the vendor prefix and
    # with transmission_sig rather than sig.
    assert set(fake.sent) >= {
        "auth_algo",
        "cert_url",
        "transmission_id",
        "transmission_sig",
        "transmission_time",
    }


def test_a_simulator_id_is_believed_in_sandbox_and_nowhere_else():
    """The simulator's events cannot be postback-verified, so a demo accepts them on their id
    alone. That is a hole with a label on it: anyone who knows the URL can post
    {"id": "WH-TEST-x", "event_type": "INVOICING.INVOICE.PAID"}. Tolerable in a sandbox,
    and on a live account it is someone trying the obvious thing.
    """
    forged = {"id": "WH-TEST-anything", "event_type": "INVOICING.INVOICE.PAID"}

    assert is_simulated(forged, sandbox=True) is True
    assert is_simulated(forged, sandbox=False) is False
    assert is_simulated({"id": "WH-SIMULATED"}, sandbox=True) is True
    assert is_simulated({"id": "WH-SIMULATED"}, sandbox=False) is False
    # A genuine event is never mistaken for a simulated one.
    assert is_simulated({"id": "WH-9AB12345"}, sandbox=True) is False
    assert is_simulated({}, sandbox=True) is False


def test_settings_know_which_environment_they_are_pointed_at():
    assert _settings(SANDBOX).is_sandbox is True
    assert _settings(LIVE).is_sandbox is False


def test_the_endpoint_refuses_a_forged_simulator_event_on_a_live_account(monkeypatch):
    """End to end: the same payload that a sandbox demo accepts must be a 400 on live."""
    from fastapi.testclient import TestClient

    from unlogged import web as web_mod

    monkeypatch.setattr(web_mod, "settings", lambda: _settings(LIVE))
    client = TestClient(web_mod.app)

    r = client.post(
        "/webhook", json={"id": "WH-TEST-forged", "event_type": "INVOICING.INVOICE.PAID"}
    )

    assert r.status_code == 400


def test_nothing_is_recorded_for_a_rejected_webhook(monkeypatch, tmp_path):
    """A rejected forgery must not reach the log the dashboard reads."""
    from fastapi.testclient import TestClient

    from unlogged import web as web_mod

    monkeypatch.setattr(web_mod, "settings", lambda: _settings(LIVE))
    monkeypatch.setattr(web_mod, "DATA", tmp_path)
    client = TestClient(web_mod.app)

    client.post("/webhook", json={"id": "WH-TEST-forged", "event_type": "INVOICING.INVOICE.PAID"})

    assert not (tmp_path / "webhooks.jsonl").exists()
