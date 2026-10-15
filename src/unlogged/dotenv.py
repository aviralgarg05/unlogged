"""Read the `.env` file the README promises this service reads.

For most of this project's life nothing did. The README said "The Python service reads
`.env`", the key went in, and the service kept running the keyword baseline while `/health`
honestly reported the baseline was live — so the setup instruction failed silently and the
evidence of the failure looked like correct behaviour.

Precedence is deliberate and is the opposite of python-dotenv's `override=True`: a variable
already in the environment always wins. `OPENAI_API_KEY= uv run ...` has to be able to force
the keyless path even when a key is sitting in `.env`, because that is how the ablation arm
and the no-credentials path are exercised, and because a loader that silently re-supplies a
deliberately-unset key turns every test run into a billable one.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load(path: Path | None = None) -> list[str]:
    """Fill absent environment variables from `path`. Returns the names actually set."""
    path = ENV_FILE if path is None else path
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        # No .env is the normal case: CI, a fresh clone, every keyless run.
        return []

    filled: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not name or name in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not value:
            # `KEY=` in the shipped .env.example is a placeholder, not a value of "".
            continue
        os.environ[name] = value
        filled.append(name)
    return filled
