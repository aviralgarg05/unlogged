import os

from fastapi.testclient import TestClient

os.environ.setdefault("UNLOGGED_REPLAY", "1")

from unlogged.web import app

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


def test_verdicts_serve_the_model_arm_from_cassettes_without_a_key():
    """A reader with no OpenAI account must still see the arm that can answer.

    This regressed once: the dashboard, /api/verdicts and every screenshot gated on the
    API key alone, so all of them showed the ablation arm billing "Unspecified work"
    against a "(Blanks)" clause. Recorded verdicts exist precisely so that cannot happen.
    """
    from unlogged.scope.adjudicate import Adjudicator
    from unlogged.web import engagement, events

    body = client.get("/api/verdicts").json()
    assert len(body["rows"]) == 8

    if Adjudicator.recorded_for(engagement(), events()):
        assert body["arm"] == "gpt-6.1-sol"
        # The model arm's whole claim is that it cites the contract. Unanimously, or the
        # screenshots are showing something weaker than what the README promises.
        assert all(r["clause_id"] for r in body["rows"])
    else:
        assert body["arm"] == "keyword-baseline"


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


def test_telemetry_round_trips_and_summarises(tmp_path, monkeypatch):
    import unlogged.web as web

    monkeypatch.setattr(web, "DATA", tmp_path)
    posted = client.post(
        "/api/telemetry",
        json={
            "events": [
                {
                    "at": "2026-10-15T00:00:00Z",
                    "type": "tool_execution_finished",
                    "tool": "read_verdicts",
                },
                {"at": "2026-10-15T00:00:01Z", "type": "run_finished"},
            ]
        },
    )
    assert posted.json() == {"ok": True, "recorded": 2}

    body = client.get("/api/telemetry").json()
    assert body["summary"]["events"] == 2
    assert body["summary"]["tool_calls"] == 1
    assert body["summary"]["tools_used"] == ["read_verdicts"]


def test_settlement_says_why_it_is_unavailable_rather_than_inventing_a_number():
    body = client.get("/api/settlement/CAP-1").json()
    assert body["available"] is False
    # The reason has to be actionable, not just a refusal.
    assert "UNLOGGED_REPLAY=0" in body["reason"]


def test_health_never_claims_a_model_it_cannot_import(monkeypatch):
    """The endpoint written to be checked during judging must not be able to lie.

    A key in the environment plus an uninstallable SDK is the one combination that made this
    service report a capability that would crash on first use.
    """
    import unlogged.config as config

    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    monkeypatch.setattr(config.Settings, "openai_importable", property(lambda self: False))

    body = client.get("/health").json()
    assert body["openai_key_set"] is True
    assert body["openai_importable"] is False
    assert body["model_configured"] is False
    assert body["adjudicator"].startswith("keyword-baseline")
    assert "not installed" in body["adjudicator"]


def test_apply_refuses_an_invoice_that_can_no_longer_take_items(monkeypatch):
    """Verified against the sandbox through this project's own dashboard: applying to a
    MARKED_AS_PAID invoice returned 500 with a stack trace, which reads as a bug here rather
    than as a closed invoice.
    """
    from unlogged.paypal import Invoices

    monkeypatch.setattr(Invoices, "get", lambda self, iid: {"status": "MARKED_AS_PAID"})
    r = client.post("/api/apply", json={"invoice_id": "INV2-X", "event_ids": ["e3"]})
    assert r.status_code == 409
    assert "MARKED_AS_PAID" in r.json()["detail"]


def test_a_part_paid_invoice_still_accepts_items():
    """PARTIALLY_PAID is not terminal — the live check adds to one and the payment survives,
    so the guard must not refuse it."""
    from unlogged.web import TERMINAL

    assert "PARTIALLY_PAID" not in TERMINAL
    assert "SENT" not in TERMINAL and "UNPAID" not in TERMINAL


def test_a_paypal_refusal_keeps_paypals_status_and_debug_id(monkeypatch):
    from unlogged.paypal import Invoices
    from unlogged.paypal.client import PayPalError

    def boom(self, iid):
        raise PayPalError(422, '{"name":"UNPROCESSABLE_ENTITY"}', debug_id="abc123")

    monkeypatch.setattr(Invoices, "get", boom)
    r = client.post("/api/apply", json={"invoice_id": "INV2-X", "event_ids": ["e3"]})
    assert r.status_code == 422
    body = r.json()
    assert body["paypal_status"] == 422
    # The one field PayPal support asks for survives the round trip.
    assert body["debug_id"] == "abc123"


def test_two_simultaneous_applies_bill_the_work_once(tmp_path, monkeypatch):
    """Reading the ledger and then writing is check-then-act. Two requests arriving together
    both saw an empty ledger, both passed the repeat check, and the client was charged twice
    for one piece of work. FastAPI runs a sync endpoint in a threadpool, so that is the
    ordinary shape of a double-click or an agent retrying its one mutating tool.
    """
    import threading
    import time

    from unlogged import web as web_mod
    from unlogged.paypal import Invoices

    monkeypatch.setattr(web_mod, "DATA", tmp_path)

    state = {"items": [{"name": "Agreed scope"}], "detail": {"currency_code": "USD"}}
    monkeypatch.setattr(
        Invoices,
        "get",
        lambda self, _id: {"status": "SENT", **state, "amount": {"value": "520.00"}},
    )

    def slow_add(self, invoice_id, items, *, notify=True, idempotency_key=None):
        time.sleep(0.05)
        state["items"] = state["items"] + [i.to_paypal() for i in items]
        return {"items": state["items"], "amount": {"value": "775.00"}}

    monkeypatch.setattr(Invoices, "add_items", slow_add)

    ready = threading.Barrier(2)
    codes = []

    def fire():
        ready.wait()
        r = client.post("/api/apply", json={"invoice_id": "INV2-RACE", "event_ids": ["e3"]})
        codes.append(r.status_code)

    threads = [threading.Thread(target=fire) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # One wins, one is refused as already billed.
    assert sorted(codes) == [200, 409], codes
    billed = [i["name"] for i in state["items"] if i["name"] != "Agreed scope"]
    assert len(billed) == 1, billed
