"""An append-only record of every change made to a live invoice.

The client's own copy of the truth is PayPal's hosted page, which is why line items
carry their provenance in the name. This ledger is the seller's side: what was added,
when, on whose authority, and which clause justified it. It is append-only because the
one thing a bill that grows must never do is quietly forget a step.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel


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

    def line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True)


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: Entry) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(entry.line() + "\n")

    def __iter__(self) -> Iterator[Entry]:
        if not self.path.exists():
            return
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                yield Entry.model_validate_json(raw)

    def total_added(self) -> Decimal:
        return sum((e.hours * e.unit_price for e in self), Decimal("0")).quantize(Decimal("0.01"))

    def summary(self) -> dict[str, Any]:
        entries = list(self)
        return {
            "changes": len(entries),
            "added": str(self.total_added()),
            "first": entries[0].at.isoformat() if entries else None,
            "last": entries[-1].at.isoformat() if entries else None,
        }


def now() -> datetime:
    return datetime.now(timezone.utc)
