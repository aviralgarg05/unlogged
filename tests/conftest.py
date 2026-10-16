"""Session-wide guards.

The committed recordings under `cassettes/` are the evidence every money claim in this
repository rests on, and a test run destroyed them once: a live code path recorded over the
demo invoice's GET, after which the documented command printed USD 1.00 instead of USD 902.50
with no error anywhere, because a matching recording existed for the corrupted state.

Recording is opt-in now, but "the mechanism is fixed" is a belief and this is a check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASSETTES = ROOT / "cassettes"


def _fingerprint() -> str:
    h = hashlib.sha256()
    for path in sorted(CASSETTES.glob("*.json")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def recordings_are_read_only():
    """Fail the run if anything under cassettes/ changed while the tests ran."""
    before = _fingerprint()
    yield
    after = _fingerprint()
    assert before == after, (
        "the test run modified cassettes/ — the committed recordings are the evidence every "
        "money claim rests on, and a suite that rewrites them can make a broken demo pass. "
        "Run `git status cassettes/` and `git checkout -- cassettes/`."
    )


@pytest.fixture(autouse=True)
def never_record(monkeypatch):
    """No test may write a recording, whatever the developer has in their environment."""
    monkeypatch.delenv("UNLOGGED_RECORD", raising=False)
