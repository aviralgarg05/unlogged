"""Re-verify every claim this project makes, and print what it found.

    uv run scripts/verify.py              # everything that needs no credentials
    uv run scripts/verify.py --live       # also re-prove the mechanism against PayPal sandbox

Written because "verified on 2026-10-15" in a README is worth less than a command a reader can
run themselves. Every claim below is checked, not asserted, and a failure is reported as a
failure rather than skipped.

--live creates a real sandbox invoice and prints its id and payer URL, so the central claim —
that an already-sent invoice grows line items while its id and QR stay valid — is re-proved on
the day you run it rather than on the day it was written.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str) -> None:
    results.append((name, status, detail))
    mark = {"PASS": "+", "FAIL": "x", "SKIP": "-"}[status]
    print(f"  {mark} {name:44} {detail}")


# Explicitly empty rather than deleted: the project fills absent variables from `.env`, so
# unsetting these would hand the credentials straight back and the section below would quietly
# stop testing the thing it is named after.
# One place, because this drifted twice: a retired invoice id left this script passing a check
# it was no longer making, and the dashboard kept quoting an invoice nobody could open.
DEMO_INVOICE = (ROOT / "fixtures" / "demo-invoice-id").read_text().strip()
EXPECTED_TOTAL = "902.50"

BLANK = {"OPENAI_API_KEY": "", "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": ""}


def run(
    *cmd: str, cwd: Path = ROOT, keyless: bool = False, data: str | None = None
) -> tuple[int, str]:
    # This file runs under `uv run --script` in its own isolated environment, so VIRTUAL_ENV
    # points somewhere the project is not installed. A nested `uv run` inherits it and resolves
    # against the wrong environment, which surfaces as a missing cassette rather than as an
    # environment error. Drop it and let uv resolve the project normally.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    if keyless:
        # Whoever runs this most often is the one person whose machine has the credentials.
        env |= BLANK
    if data:
        env["UNLOGGED_DATA"] = data
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr).strip()


def _why(code: int, out: str) -> str:
    """A failure should say what went wrong, not just that something did."""
    import re as _re

    m = _re.search(r"No cassette for ([^\n]*)", out)
    if m:
        return f"exit {code}: missing {m.group(1)[:80]}"
    last = out.strip().splitlines()[-1][:60] if out.strip() else "no output"
    return f"exit {code}: {last}"


def section(title: str) -> None:
    print(f"\n{title}")
    print("─" * 72)


def offline() -> None:
    section("Runs with no credentials — the Stage One requirement")

    code, out = run("uv", "run", "pytest", "-q", keyless=True)
    summary = next(
        (line for line in reversed(out.splitlines()) if "passed" in line or "failed" in line), ""
    )
    check("test suite", PASS if code == 0 else FAIL, summary.strip()[:60])

    code, _ = run("uv", "run", "ruff", "check", "src", "tests", "scripts", keyless=True)
    check("lint", PASS if code == 0 else FAIL, "ruff check")

    code, _ = run("uv", "run", "ruff", "format", "--check", "src", "tests", keyless=True)
    check("formatting", PASS if code == 0 else FAIL, "ruff format --check")

    # The evaluation is the project's central empirical claim; it must reproduce exactly.
    code, out = run(
        "uv",
        "run",
        "unlogged",
        "evaluate",
        "--engagement",
        "fixtures/engagement.json",
        "--events",
        "fixtures/events.jsonl",
        "--gold",
        "fixtures/gold.jsonl",
        keyless=True,
    )
    rows = {
        line.split("|")[1].strip(): line.strip()
        for line in out.splitlines()
        if line.startswith("| keyword") or line.startswith("| gpt-")
    }
    # Pinned whole rather than by substring: a column added to the report used to slip past
    # this check, which is how a $42.50 hour error stayed invisible for as long as it did.
    expected = "| keyword-baseline | 12% | 0% | 0% | 2 | 2 | 0 | $170.00 | $425.00 | 0 | $0.00 |"
    check(
        "baseline reproduces exactly",
        PASS if rows.get("keyword-baseline") == expected else FAIL,
        (rows.get("keyword-baseline") or "no row")[:58],
    )
    # The model arm must replay from recorded verdicts, or a judge with no OpenAI account
    # only ever sees the arm built to lose.
    model = next((v for k, v in rows.items() if k.startswith("gpt-")), "")
    check(
        "model arm replays without a key",
        PASS if "100%" in model else FAIL,
        model[:58] or "model arm absent",
    )

    code, out = run(
        "uv",
        "run",
        "unlogged",
        "discover",
        "--engagement",
        "fixtures/engagement.json",
        "--events",
        "fixtures/events.jsonl",
        "--invoice-id",
        DEMO_INVOICE,
        "--apply",
        keyless=True,
        # Its own ledger: the apply flow refuses work already billed to this invoice, so a
        # repeat run against the project's own ledger is correctly refused and this check
        # would be exercising the guard instead of the flow.
        data=TemporaryDirectory().name,
    )
    total = next((line for line in out.splitlines() if "Total now" in line), "")
    check(
        "full apply flow replays from cassettes",
        PASS if EXPECTED_TOTAL in total else FAIL,
        total.strip()[:60] or _why(code, out),
    )

    # Every number in the README that a reader could check against a command. This project's
    # whole argument is that its claims are runnable, so a stale figure is not a typo — it is
    # the one kind of error that discredits everything beside it. Six of them had drifted.
    readme = (ROOT / "README.md").read_text()
    flat = " ".join(readme.replace("*", "").split())
    stale = [r for r in rows.values() if " ".join(r.replace("*", "").split()) not in flat]
    check(
        "README quotes the eval table it generates",
        PASS if not stale else FAIL,
        "both arms match" if not stale else f"{len(stale)} row(s) differ",
    )

    code, tout = run("uv", "run", "pytest", "-q", keyless=True)
    m = re.search(r"(\d+) passed", tout)
    ran = m.group(1) if m else "?"
    check(
        "README quotes the test count it has",
        PASS if f"# {ran} tests" in readme else FAIL,
        f"{ran} passing",
    )

    section("Submission requirements")

    lic = ROOT / "LICENSE"
    first = lic.read_text().splitlines()[0] if lic.exists() else ""
    check("LICENSE present and detectable", PASS if "MIT" in first else FAIL, first[:40])

    code, out = run("git", "ls-files")
    tracked = set(out.split())
    leaked = [f for f in tracked if f == ".env" or f.endswith("/.env.local")]
    check("no key file is tracked", PASS if not leaked else FAIL, ", ".join(leaked) or "clean")

    # Assembled rather than written out, so this file does not match its own pattern.
    key_pattern = "sk" + "-proj|" + "sk" + "-[A-Za-z0-9]{32}"
    code, out = run("git", "grep", "-lE", key_pattern, "--", ".")
    # git grep exits 1 when it finds nothing, which is the outcome we want.
    check("no API key in any tracked file", PASS if code != 0 else FAIL, out[:40] or "clean")

    cassettes = list((ROOT / "cassettes").glob("*.json"))
    check(
        "cassettes present for the keyless path",
        PASS if cassettes else FAIL,
        f"{len(cassettes)} recorded exchanges",
    )

    # Counted rather than written down, because this sentence has been wrong twice and a
    # README that miscounts its own checks is the first thing a careful reader stops trusting.
    keyless = len(results) + 1
    check(
        "README quotes the number of checks it runs",
        PASS if f"{keyless} checks keyless," in readme else FAIL,
        f"{keyless} keyless",
    )


DOTENV_PROBE = (
    "from unlogged.config import Settings; "
    "print('ready' if Settings.from_env().has_paypal else 'no')"
)


def live() -> None:
    section("Live against PayPal sandbox — the central claim, re-proved today")

    # Credentials reach the project through `.env`, which is where the README tells the
    # reader to put them. Reading only the process environment meant `--live` skipped itself
    # for anyone who followed those instructions, and reported the skip as though they had
    # simply not set anything.
    code, out = run("uv", "run", "python", "-c", DOTENV_PROBE)
    if out.strip() != "ready":
        check("live mechanism", SKIP, "no PayPal credentials in the environment or .env")
        return

    # Run through the project's own environment rather than this script's. Everything else
    # here shells out too, so this stays consistent and the script keeps one dependency.
    code, out = run("uv", "run", "python", str(Path(__file__).parent / "_live_check.py"))
    for line in out.splitlines():
        if line.startswith("CHECK\t"):
            _, name, status, detail = line.split("\t", 3)
            check(name, status, detail)
        elif line.startswith("PAYER\t"):
            print(f"\n  payer page: {line.split(chr(9), 1)[1]}")
    if code != 0 and not any(r[0].startswith("a sent invoice") for r in results):
        check("live mechanism", FAIL, out.splitlines()[-1][:60] if out else "no output")


def live_total() -> None:
    """The second half of that sentence, checked where the live checks have actually run.

    Asserting it keylessly meant hardcoding how many checks the live script emits, which is
    the same guess the sentence itself was making.
    """
    readme = (ROOT / "README.md").read_text()
    total = len(results) + 1
    check(
        "README quotes the number of checks with credentials",
        PASS if f"{total} with sandbox credentials" in readme else FAIL,
        f"{total} with credentials",
    )


def main() -> int:
    print(f"unlogged — verification run, {date.today().isoformat()}")
    offline()
    if "--live" in sys.argv:
        live()
        live_total()

    failed = [r for r in results if r[1] == FAIL]
    skipped = [r for r in results if r[1] == SKIP]
    print(
        f"\n{len(results) - len(failed) - len(skipped)} passed, "
        f"{len(failed)} failed, {len(skipped)} skipped"
    )
    if failed:
        print("\nFailures:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
    (ROOT / "docs" / "verification.json").write_text(
        json.dumps(
            {"date": date.today().isoformat(), "results": [list(r) for r in results]}, indent=1
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
