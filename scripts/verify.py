# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
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
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str) -> None:
    results.append((name, status, detail))
    mark = {"PASS": "+", "FAIL": "x", "SKIP": "-"}[status]
    print(f"  {mark} {name:44} {detail}")


def run(*cmd: str, cwd: Path = ROOT) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def section(title: str) -> None:
    print(f"\n{title}")
    print("─" * 72)


def offline() -> None:
    section("Runs with no credentials — the Stage One requirement")

    code, out = run("uv", "run", "pytest", "-q")
    summary = next(
        (line for line in reversed(out.splitlines()) if "passed" in line or "failed" in line), ""
    )
    check("test suite", PASS if code == 0 else FAIL, summary.strip()[:60])

    code, _ = run("uv", "run", "ruff", "check", "src", "tests", "scripts")
    check("lint", PASS if code == 0 else FAIL, "ruff check")

    code, _ = run("uv", "run", "ruff", "format", "--check", "src", "tests")
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
    )
    row = next((line for line in out.splitlines() if line.startswith("| keyword")), "")
    expected = "| keyword-baseline | 12% | 0% | 0% | 2 | 2 | 0 | $170.00 | $425.00 |"
    check(
        "evaluation reproduces exactly",
        PASS if row.strip() == expected else FAIL,
        row.strip()[:60] or "no row produced",
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
        "INV2-MSMM-CLAS-Z36Z-CXSH",
        "--apply",
    )
    total = next((line for line in out.splitlines() if "Total now" in line), "")
    check(
        "full apply flow replays from cassettes",
        PASS if "690.00" in total else FAIL,
        total.strip()[:60] or "no total",
    )

    section("Submission requirements")

    lic = ROOT / "LICENSE"
    first = lic.read_text().splitlines()[0] if lic.exists() else ""
    check("LICENSE present and detectable", PASS if "MIT" in first else FAIL, first[:40])

    code, out = run("git", "ls-files")
    tracked = set(out.split())
    leaked = [f for f in tracked if f == ".env" or f.endswith("/.env.local")]
    check("no key file is tracked", PASS if not leaked else FAIL, ", ".join(leaked) or "clean")

    code, out = run("git", "grep", "-lE", "sk-proj|sk-[A-Za-z0-9]{32}", "--", ".")
    # git grep exits 1 when it finds nothing, which is the outcome we want.
    check("no API key in any tracked file", PASS if code != 0 else FAIL, out[:40] or "clean")

    cassettes = list((ROOT / "cassettes").glob("*.json"))
    check(
        "cassettes present for the keyless path",
        PASS if cassettes else FAIL,
        f"{len(cassettes)} recorded exchanges",
    )


def live() -> None:
    section("Live against PayPal sandbox — the central claim, re-proved today")

    if not (os.environ.get("PAYPAL_CLIENT_ID") and os.environ.get("PAYPAL_CLIENT_SECRET")):
        check("live mechanism", SKIP, "set PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET")
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


def main() -> int:
    print(f"unlogged — verification run, {date.today().isoformat()}")
    offline()
    if "--live" in sys.argv:
        live()

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
