"""The cassette layer.

This is what makes the project runnable by someone with no PayPal account, which Stage One of
the hackathon is pass/fail on. It is worth testing directly rather than only through the things
that use it.
"""

import json
from pathlib import Path

import pytest

from unlogged.config import Settings
from unlogged.paypal import client as client_mod
from unlogged.paypal.client import PayPalClient, PayPalError, _cassette_key


def settings(**kw) -> Settings:
    base = {
        "client_id": "",
        "client_secret": "",
        "base_url": "https://api-m.sandbox.paypal.com",
        "openai_api_key": None,
        "replay": True,
    }
    return Settings(**{**base, **kw})


@pytest.fixture
def cassettes(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(client_mod, "CASSETTES", tmp_path)
    return tmp_path


def record(dir_: Path, method: str, path: str, body, status: int, payload) -> str:
    key = _cassette_key(method, path, body)
    (dir_ / f"{key}.json").write_text(json.dumps({"status": status, "body": payload}))
    return key


def test_a_recorded_exchange_replays_without_credentials(cassettes: Path):
    record(cassettes, "GET", "/v2/invoicing/invoices/INV2-X", None, 200, {"id": "INV2-X"})
    with PayPalClient(settings()) as c:
        assert c.request("GET", "/v2/invoicing/invoices/INV2-X") == {"id": "INV2-X"}


def test_a_recorded_failure_replays_as_a_failure(cassettes: Path):
    """A cassette that recorded a 500 must not replay as a success."""
    record(
        cassettes, "POST", "/v2/invoicing/invoices/X/conditional-rules", None, 500, {"name": "E"}
    )
    with PayPalClient(settings()) as c, pytest.raises(PayPalError) as exc:
        c.request("POST", "/v2/invoicing/invoices/X/conditional-rules")
    assert exc.value.status == 500


def test_a_missing_cassette_says_how_to_record_one(cassettes: Path):
    with PayPalClient(settings()) as c, pytest.raises(PayPalError) as exc:
        c.request("GET", "/v2/invoicing/invoices/NOPE")
    assert "UNLOGGED_REPLAY=0" in str(exc.value)


def test_replay_is_forced_when_there_are_no_credentials(cassettes: Path):
    """Even with replay off, no credentials means no live call — not a crash mid-request."""
    record(cassettes, "GET", "/x", None, 200, {"ok": True})
    with PayPalClient(settings(replay=False)) as c:
        assert c.request("GET", "/x") == {"ok": True}


def test_the_cassette_key_distinguishes_different_requests():
    a = _cassette_key("PUT", "/v2/invoicing/invoices/X", {"items": [1]})
    b = _cassette_key("PUT", "/v2/invoicing/invoices/X", {"items": [1, 2]})
    c = _cassette_key("GET", "/v2/invoicing/invoices/X", {"items": [1]})
    assert len({a, b, c}) == 3


def test_the_cassette_key_ignores_key_order():
    """Two bodies that mean the same thing must hit the same cassette."""
    assert _cassette_key("PUT", "/x", {"a": 1, "b": 2}) == _cassette_key(
        "PUT", "/x", {"b": 2, "a": 1}
    )
