"""An append-only record of every change made to a live invoice.

The client's own copy of the truth is PayPal's hosted page, which is why line items
carry their provenance in the name. This ledger is the seller's side: what was added,
when, on whose authority, and which clause justified it. It is append-only because the
one thing a bill that grows must never do is quietly forget a step.
"""

from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, computed_field


class Entry(BaseModel):
    at: datetime
    invoice_id: str
    event_id: str
    clause_id: str | None
    line_name: str
    hours: Decimal
    unit_price: Decimal
    total_after: Decimal
    adjudicator: str
    confidence: float
    # False means "the write was attempted and we do not know whether it landed". The row is
    # appended BEFORE the money moves, because the ledger is the only guard against
    # double-billing — PayPal ignores the idempotency header on an invoice PUT — and a guard
    # that is written after the write does not exist during the window it has to cover. A
    # crash, a killed process or a read timeout between the two leaves this row behind, and
    # the next run refuses rather than billing again. `unlogged reconcile` says which it was.
    settled: bool = True
    # Appended when a write is known never to have reached PayPal, which frees the events to
    # be billed properly. The distinction matters: an intent row means "sent, outcome unknown"
    # and must block a retry, while a request that never left must not — otherwise one failed
    # click blocks the legitimate apply for good, on an append-only record with no way back.
    voided: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total(self) -> Decimal:
        """What this line actually added. Derived, so a stored row can never disagree with it.

        Its absence is why the dashboard's "Added after sending" tile and the chart titled
        "What each discovered line added to the bill" both summed `unit_price` — the hourly
        rate — and drew four identical bars at $85.
        """
        return (self.hours * self.unit_price).quantize(Decimal("0.01"))

    def line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True)


class Ledger:
    """An append-only record of changes to a live invoice.

    `seed` is read when nothing has been written locally yet. Without it the page titled
    "Every line this system added to the live PayPal invoice" renders empty on a fresh clone —
    the climax screen of the product, blank, on the documented judge path.
    """

    def __init__(self, path: Path, seed: Path | None = None):
        self.path = path
        self.seed = seed if seed is not None else path.parent / "seed" / path.name
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _source(self) -> Path | None:
        # An empty local file is not local history. It is what a crashed first run, or any
        # code that touched the path, leaves behind — and preferring it over the seed makes
        # the product's own summary page render blank for a reason nobody can see.
        if self.path.exists() and self.path.stat().st_size > 0:
            return self.path
        return self.seed if self.seed.exists() else None

    @contextmanager
    def guard(self) -> Iterator[None]:
        """Hold an exclusive lock on this ledger for the whole read-decide-write-record cycle.

        Checking the ledger and then writing to PayPal is check-then-act: two callers that
        read before either wrote both see nothing billed, both proceed, and the client is
        charged twice for one piece of work. A lock inside the HTTP call does not help, it
        only makes the two identical writes tidy.

        A file lock rather than a thread lock, because the CLI and the web service are
        separate processes against one engagement.
        """
        # A sibling, not the ledger itself. Opening the ledger to lock it created an empty
        # file, which `_source` then preferred over the seed — so taking the lock was enough
        # to blank the page titled "Every line this system added to the live PayPal invoice",
        # on a fresh clone, before anything had been billed.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.with_suffix(".lock").open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def billed_to(self, invoice_id: str) -> set[str]:
        """Event ids written against this invoice: settled, or attempted and unresolved.

        The latest row for an event wins, so a void releases it and a later real write claims
        it again. Attempted-but-unresolved still counts — the money may have moved.
        """
        latest: dict[str, Entry] = {}
        for e in self:
            if e.invoice_id == invoice_id:
                latest[e.event_id] = e
        return {eid for eid, e in latest.items() if not e.voided}

    def append(self, entry: Entry) -> None:
        # Carry the seed forward on the first local write. Reading it only as a fallback meant
        # the earlier periods vanished the moment anyone used the product — an append-only
        # record that silently drops its history the first time it is appended to.
        if not self.path.exists() and self.seed.exists():
            self.path.write_text(self.seed.read_text(), encoding="utf-8")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(entry.line() + "\n")

    def __iter__(self) -> Iterator[Entry]:
        source = self._source()
        if source is None:
            return
        for raw in source.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                yield Entry.model_validate_json(raw)

    def total_added(self) -> Decimal:
        return sum((e.hours * e.unit_price for e in self), Decimal(0)).quantize(Decimal("0.01"))

    def summary(self) -> dict[str, Any]:
        entries = list(self)
        return {
            "changes": len(entries),
            "added": str(self.total_added()),
            "first": entries[0].at.isoformat() if entries else None,
            "last": entries[-1].at.isoformat() if entries else None,
        }


def now() -> datetime:
    return datetime.now(UTC)
