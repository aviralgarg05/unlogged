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

A directory of recordings is therefore a shared, ordered resource, and the two hazards that
follow from that are handled below rather than left as comments: a filename that does not
parse as a take (`_TAKE`), and more than one writer (`_Recorder`).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
import warnings
from pathlib import Path
from typing import IO, Any

DIR = Path(__file__).resolve().parents[2] / "cassettes"

#: A take's suffix, read strictly. See `takes`.
_TAKE = re.compile(r"(?P<n>\d+)\.json")


def key(payload: Any) -> str:
    """Stable id for an exchange. Volatile fields are excluded by the caller, not here.

    One argument, serialised directly. Taking *parts and hashing the tuple would wrap the
    payload in a list, change every digest, and orphan every cassette already committed —
    which is exactly what happened when this moved out of the PayPal client.
    """
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


def takes(k: str, root: Path | None = None) -> list[Path]:
    """Every recorded response for a key, in the order it was recorded.

    Take numbers are read with a strict pattern, and anything else carrying the key's name is
    skipped with a warning. The glob this replaced, `k.[0-9]*.json`, also matched `k.2x.json`
    and then died inside `int()` — so one mistyped or half-copied filename in a committed
    directory took down every replay of that key, with a `ValueError` naming neither the file
    nor the reason, in a repo whose whole promise is that it runs with no credentials.

    A take number used twice is refused rather than resolved. `k.1.json` and `k.01.json` are
    both take 1, and quietly preferring one of them decides which invoice total a reader is
    shown — the kind of choice this project will not make silently.
    """
    root = DIR if root is None else root
    if not root.is_dir():
        return []
    first = root / f"{k}.json"
    numbered: dict[int, Path] = {}
    for path in sorted(root.iterdir()):
        if path == first or not path.name.startswith(f"{k}."):
            continue
        match = _TAKE.fullmatch(path.name[len(k) + 1 :])
        if match is None:
            warnings.warn(f"{path.name} is not a cassette take and is being ignored", stacklevel=2)
            continue
        n = int(match["n"])
        clash = numbered.get(n) or (first if n == 0 and first.exists() else None)
        if clash is not None:
            raise ValueError(
                f"{path.name} and {clash.name} are both take {n} of this key; "
                f"replaying either one would silently pick which recording wins"
            )
        numbered[n] = path
    return ([first] if first.exists() else []) + [numbered[n] for n in sorted(numbered)]


class _Recorder:
    """This process's claim on one directory of recordings, and its take numbering.

    Both belong to the directory, not to a `Tape`. Two tapes recording the same key each
    believed it was writing take 0: the second unlinked the first's `k.json` and wrote its
    own, and then the first wrote `k.1.json` — leaving a sequence spliced out of two writers,
    which replays as one coherent tape with the total from one of them and the lines from the
    other. That is the worst shape a fault can take here, because nothing fails.

    `fcntl.flock` extends the same claim across processes, which cannot see this dict. A
    second recorder is refused rather than queued: a recording run is a developer action, and
    waiting for another one to finish would only interleave the two tapes more politely. The
    lock is held on a sibling file, never inside the directory, so it is not mistaken for a
    recording and cannot change what a replay sees. A killed process releases it; the kernel
    owns the lock, not the file, so a leftover `.cassettes.lock` is inert.
    """

    def __init__(self, root: Path):
        self.root = root
        self.counts: dict[str, int] = {}
        root.mkdir(parents=True, exist_ok=True)
        self._lock: IO[str] = (root.parent / f".{root.name}.lock").open("w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock.close()
            raise RuntimeError(
                f"another process is already recording into {root}. Two recorders splice one "
                f"key's takes together into a tape that replays without complaining, so the "
                f"second is refused. Finish or stop the other run first."
            ) from exc

    def take(self, k: str) -> int:
        n = self.counts.get(k, 0)
        self.counts[k] = n + 1
        return n

    def release(self) -> None:
        fcntl.flock(self._lock, fcntl.LOCK_UN)
        self._lock.close()


_RECORDERS: dict[Path, _Recorder] = {}


def _recorder(root: Path) -> _Recorder:
    resolved = root.resolve()
    if resolved not in _RECORDERS:
        _RECORDERS[resolved] = _Recorder(resolved)
    return _RECORDERS[resolved]


def forget_run(root: Path | None = None) -> None:
    """End this process's recording run, so the next record starts a fresh one.

    With no argument it drops every claim this process holds, which is what a run is: the
    process. Nothing in the product calls it — a process exits and the kernel does this.

    It exists for tests. Proving that re-recording replaces a key's whole sequence takes two
    runs, and a second `Tape` in the same process is deliberately no longer one of those; and
    a test suite is one process that records into many directories, so without an end to each
    run it would hold an open descriptor per directory until it exits.
    """
    claimed = list(_RECORDERS) if root is None else [root.resolve()]
    for path in claimed:
        recorder = _RECORDERS.pop(path, None)
        if recorder is not None:
            recorder.release()


class Tape:
    """One run's position in the recordings. Per-instance, so one client's sequence of
    requests lines up with one recorded sequence."""

    def __init__(self, root: Path | None = None):
        self.root = DIR if root is None else root
        self._replays: dict[str, int] = {}

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
        """Append this run's next take for a key, replacing any earlier run's sequence.

        The take number comes from the directory's recorder, not from this tape, so two
        clients recording in one run extend one sequence instead of overwriting each other.
        """
        recorder = _recorder(self.root)
        n = recorder.take(k)
        if n == 0:
            # Everything in this key's namespace, not just what `takes` will parse: a stray
            # `k.2x.json` left by a hand-edit would otherwise outlive the tape it belongs to
            # and warn on every replay from here on.
            for stale in sorted(recorder.root.glob(f"{k}.*")):
                stale.unlink()
        dest = recorder.root / (f"{k}.json" if n == 0 else f"{k}.{n}.json")
        dest.write_text(json.dumps(payload, indent=1))
        return dest
