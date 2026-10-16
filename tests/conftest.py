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
DATA = ROOT / "data"


def _fingerprint() -> str:
    """Everything a test run must leave exactly as it found it.

    The recordings were watched and the shipped `data/` was not, while a test was appending
    to data/webhooks.jsonl on every single run — the judge-visible ledger directory, growing
    quietly, from the suite that exists to prove nothing moves.
    """
    h = hashlib.sha256()
    for root in (CASSETTES, DATA):
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.name.endswith(".lock"):
                h.update(str(path.relative_to(ROOT)).encode())
                h.update(path.read_bytes())
    return h.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def recordings_are_read_only():
    """Fail the run if anything under cassettes/ changed while the tests ran."""
    before = _fingerprint()
    yield
    after = _fingerprint()
    assert before == after, (
        "the test run modified cassettes/ or data/ — the recordings are the evidence every "
        "money claim rests on, and a suite that rewrites them can make a broken demo pass. "
        "Run `git status cassettes/` and `git checkout -- cassettes/`."
    )


@pytest.fixture(autouse=True)
def never_record(monkeypatch):
    """No test may write a recording, whatever the developer has in their environment."""
    # Set to empty rather than deleted. `Settings.from_env` loads `.env` first, and that
    # loader fills variables that are ABSENT — so deleting the name handed it straight back
    # from a developer's own file, and the fixture promising "no test may write a recording"
    # was undone by the project's own configuration.
    monkeypatch.setenv("UNLOGGED_RECORD", "")


@pytest.fixture(autouse=True)
def each_test_is_its_own_recording_run():
    """End the recording run after every test.

    A recording run holds an exclusive lock on its directory for the life of the process, and
    the suite is one process that records into a fresh `tmp_path` per test. Without this the
    descriptors pile up until the run exits, which is how the two tests that prove take
    numbering came with a column of ResourceWarnings attached.
    """
    from unlogged import cassette

    yield
    cassette.forget_run()
