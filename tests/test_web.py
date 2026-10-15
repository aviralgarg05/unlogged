import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("UNLOGGED_REPLAY", "1")

from unlogged.web import app  # noqa: E402

client = TestClient(app)


def test_health_reports_which_adjudicator_is_live():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Without a key the baseline is the live arm, and /health says so rather than pretending.
    assert body["adjudicator"] in ("keyword-baseline", "gpt-6.1-sol")


def test_engagement_exposes_the_payer_note_the_client_actually_sees():
    body = client.get("/api/engagement").json()
    assert body["cap"] == "1200.00"
    assert "Agreed cap USD 1,200.00" in body["payer_note"]
    assert len(body["clauses"]) == 5


def test_events_are_paged_server_side():
    first = client.get("/api/events", params={"page": 1, "page_size": 3}).json()
    assert first["total"] == 8
    assert len(first["rows"]) == 3
    second = client.get("/api/events", params={"page": 2, "page_size": 3}).json()
    assert len(second["rows"]) == 3
    assert {r["id"] for r in first["rows"]}.isdisjoint({r["id"] for r in second["rows"]})


def test_verdicts_name_their_arm():
    body = client.get("/api/verdicts").json()
    assert body["arm"] == "keyword-baseline"
    assert len(body["rows"]) == 8


def test_apply_refuses_when_nothing_selected_is_billable():
    r = client.post("/api/apply", json={"invoice_id": "INV2-X", "event_ids": ["e2"]})
    assert r.status_code == 400


def test_webhook_rejects_an_unverified_payload():
    r = client.post("/webhook", json={"event_type": "INVOICING.INVOICE.PAID", "id": "WH-REAL"})
    assert r.status_code == 400


def test_webhook_accepts_a_simulated_event_and_marks_it_as_simulated():
    r = client.post("/webhook", json={"event_type": "INVOICING.INVOICE.PAID", "id": "WH-SIMULATED"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "verified": False, "simulated": True}
