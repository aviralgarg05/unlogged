"""A thin PayPal REST client.

Everything here that looks like a quirk is one, verified against the sandbox on
2026-10-15. See docs/VERIFIED.md for the raw exchanges.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Self

import httpx
import structlog

from unlogged import cassette
from unlogged.config import Settings

log = structlog.get_logger(__name__)

CASSETTES = Path(__file__).resolve().parents[3] / "cassettes"


class PayPalError(RuntimeError):
    def __init__(self, status: int, body: str, debug_id: str | None = None):
        self.status, self.body, self.debug_id = status, body, debug_id
        super().__init__(f"PayPal {status}: {body[:400]}")

    @property
    def never_dispatched(self) -> bool:
        """True when the request did not leave this process.

        Only the missing-cassette case qualifies: it is raised before any socket is opened, so
        nothing can have been billed. Everything else — a timeout, a 5xx, a dropped connection
        — may have applied at PayPal's end, and treating those as "never happened" is how an
        integration bills a client twice.
        """
        return self.status == 0 and "No cassette" in self.body


def _cassette_key(method: str, path: str, body: Any) -> str:
    """Stable id for a recorded exchange. Volatile fields are excluded by the caller."""
    return cassette.key({"m": method, "p": path, "b": body})


class PayPalClient:
    """OAuth2 client-credentials, with cassette replay for the keyless judge path."""

    def __init__(self, settings: Settings, *, timeout: float = 60.0):
        self.s = settings
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._http = httpx.Client(timeout=timeout)
        # One tape per client, so this run's sequence of requests lines up with one
        # recorded sequence.
        self.tape = cassette.Tape(CASSETTES)

    # -- auth ---------------------------------------------------------------

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        r = self._http.post(
            f"{self.s.base_url}/v1/oauth2/token",
            auth=(self.s.client_id, self.s.client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            raise PayPalError(r.status_code, r.text)
        body = r.json()
        self._token = body["access_token"]
        # Refresh a minute early rather than racing the expiry.
        self._expires_at = time.monotonic() + max(60.0, float(body.get("expires_in", 32400)) - 60)
        return self._token

    # -- requests -----------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        representation: bool = True,
        idempotency: str | None = None,
        raw: bool = False,
        final: bool = False,
    ) -> Any:
        """Call PayPal, or replay a recorded exchange when running keyless.

        `representation` sends `Prefer: return=representation` — without it a create
        returns a minimal body and the id has to be scraped out of the Location header.
        `idempotency` becomes PayPal-Request-Id; the official agent toolkit never sets it.
        """
        key = _cassette_key(method, path, json_body)

        if self.s.replay or not self.s.has_paypal:
            rec = self.tape.final(key) if final else self.tape.replay(key)
            if rec is None:
                raise PayPalError(
                    0,
                    f"No cassette for {method} {path} ({key}). Set UNLOGGED_REPLAY=0 with "
                    f"PayPal sandbox credentials to record one.",
                )
            if rec["status"] >= 400:
                raise PayPalError(rec["status"], json.dumps(rec["body"]))
            return rec["body"]

        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
        }
        if representation:
            headers["Prefer"] = "return=representation"
        if idempotency:
            headers["PayPal-Request-Id"] = idempotency

        r = self._http.request(
            method, f"{self.s.base_url}{path}", headers=headers, json=json_body, params=params
        )
        log.debug("paypal", method=method, path=path, status=r.status_code)

        if r.status_code >= 400:
            # PayPal returns a debug_id on most errors and it is the only thing their support
            # will ask for, so it is worth pulling out — but an error body is not always JSON.
            debug_id = None
            if r.headers.get("content-type", "").startswith("application/json"):
                debug_id = r.json().get("debug_id")
            raise PayPalError(r.status_code, r.text, debug_id)

        if raw:
            payload: Any = {"_raw_b64": r.content.hex(), "_ct": r.headers.get("content-type", "")}
        else:
            payload = r.json() if r.content else {}

        if self.s.record:
            self.tape.record(key, {"status": r.status_code, "body": payload})
        return payload

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
