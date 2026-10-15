"""A thin PayPal REST client.

Everything here that looks like a quirk is one, verified against the sandbox on
2026-10-15. See docs/VERIFIED.md for the raw exchanges.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Self

import httpx
import structlog

from unlogged.config import Settings

log = structlog.get_logger(__name__)

CASSETTES = Path(__file__).resolve().parents[3] / "cassettes"


def _takes(key: str) -> list[Path]:
    """Every recorded response for a key, in the order it was recorded."""
    first = CASSETTES / f"{key}.json"
    rest = sorted(CASSETTES.glob(f"{key}.[0-9]*.json"), key=lambda q: int(q.suffixes[-2][1:]))
    return ([first] if first.exists() else []) + rest


class PayPalError(RuntimeError):
    def __init__(self, status: int, body: str, debug_id: str | None = None):
        self.status, self.body, self.debug_id = status, body, debug_id
        super().__init__(f"PayPal {status}: {body[:400]}")


def _cassette_key(method: str, path: str, body: Any) -> str:
    """Stable id for a recorded exchange. Volatile fields are excluded by the caller."""
    blob = json.dumps({"m": method, "p": path, "b": body}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


class PayPalClient:
    """OAuth2 client-credentials, with cassette replay for the keyless judge path."""

    def __init__(self, settings: Settings, *, timeout: float = 60.0):
        self.s = settings
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._http = httpx.Client(timeout=timeout)
        # Per-key positions, so one client's run of requests lines up with one recorded run.
        self._replays: dict[str, int] = {}
        self._records: dict[str, int] = {}

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
    ) -> Any:
        """Call PayPal, or replay a recorded exchange when running keyless.

        `representation` sends `Prefer: return=representation` — without it a create
        returns a minimal body and the id has to be scraped out of the Location header.
        `idempotency` becomes PayPal-Request-Id; the official agent toolkit never sets it.
        """
        key = _cassette_key(method, path, json_body)

        if self.s.replay or not self.s.has_paypal:
            takes = _takes(key)
            if not takes:
                raise PayPalError(
                    0,
                    f"No cassette for {method} {path} ({key}). Set UNLOGGED_REPLAY=0 with "
                    f"PayPal sandbox credentials to record one.",
                )
            # The i-th request for a key replays the i-th recorded response, because a key is
            # method+path+body and the invoice this project exists to grow is fetched before
            # the write and again after it. Keyed only by name, the second GET overwrote the
            # first and replay could not reproduce a change in state at all — the one thing
            # the recordings are kept for. Reads past the end hold at the final state.
            i = self._replays.get(key, 0)
            self._replays[key] = i + 1
            rec = json.loads(takes[min(i, len(takes) - 1)].read_text())
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

        CASSETTES.mkdir(parents=True, exist_ok=True)
        n = self._records.get(key, 0)
        if n == 0:
            # Re-recording replaces a key's whole sequence rather than interleaving this run's
            # responses with a previous run's.
            for stale in _takes(key):
                stale.unlink()
        self._records[key] = n + 1
        dest = CASSETTES / (f"{key}.json" if n == 0 else f"{key}.{n}.json")
        dest.write_text(json.dumps({"status": r.status_code, "body": payload}, indent=1))
        return payload

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
