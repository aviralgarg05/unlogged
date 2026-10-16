"""Recorded HTTP exchanges, replayed so the project runs with no credentials.

Every claim this repo makes is supposed to be checkable by someone who has no PayPal
account, no OpenAI key and no GitHub token. That only works if each outbound call can be
replayed from something committed, which is what a cassette is.

Two properties matter and both were learned the hard way:

* A key can hold MORE THAN ONE recorded response, replayed in the order they were recorded.
  The invoice this project exists to grow is read before the write and again after it, under
  the same method and path. Keyed by name alone the second read overwrote the first, and the
  recordings could not reproduce a total going up — the one thing they are kept for.
* Re-recording a key REPLACES its whole sequence rather than interleaving this run's
  responses with a previous run's.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parents[2] / "cassettes"


def key(payload: Any) -> str:
    """Stable id for an exchange. Volatile fields are excluded by the caller, not here.

    One argument, serialised directly. Taking *parts and hashing the tuple would wrap the
    payload in a list, change every digest, and orphan every cassette already committed —
    which is exactly what happened when this moved out of the PayPal client.
    """
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def takes(k: str, root: Path | None = None) -> list[Path]:
    """Every recorded response for a key, in the order it was recorded."""
    root = DIR if root is None else root
    first = root / f"{k}.json"
    rest = sorted(root.glob(f"{k}.[0-9]*.json"), key=lambda p: int(p.suffixes[-2][1:]))
    return ([first] if first.exists() else []) + rest


class Tape:
    """One run's position in the recordings. Per-instance, so one client's sequence of
    requests lines up with one recorded sequence."""

    def __init__(self, root: Path | None = None):
        self.root = DIR if root is None else root
        self._replays: dict[str, int] = {}
        self._records: dict[str, int] = {}

    def replay(self, k: str) -> dict[str, Any] | None:
        """The next recorded response for this key, or None if nothing was ever recorded.

        Reads past the end hold at the final state rather than failing: a caller that reads
        an unchanged resource twice should not need two identical recordings.
        """
        available = takes(k, self.root)
        if not available:
            return None
        i = self._replays.get(k, 0)
        self._replays[k] = i + 1
        return json.loads(available[min(i, len(available) - 1)].read_text())

    def final(self, k: str) -> dict[str, Any] | None:
        """The LAST recorded response for a key, ignoring this run's position.

        A recording is a tape of a past session, and for a caller asking "what does this
        resource look like now" the answer the tape can give is where it ended. Reconciling a
        ledger against the first take compares a record of what was written against a snapshot
        taken before any of it was — which reports every correct invoice as diverged.
        """
        available = takes(k, self.root)
        if not available:
            return None
        return json.loads(available[-1].read_text())

    def record(self, k: str, payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        n = self._records.get(k, 0)
        if n == 0:
            for stale in takes(k, self.root):
                stale.unlink()
        self._records[k] = n + 1
        dest = self.root / (f"{k}.json" if n == 0 else f"{k}.{n}.json")
        dest.write_text(json.dumps(payload, indent=1))
        return dest
