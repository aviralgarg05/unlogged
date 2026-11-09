"""Set up the demo video's hero shot, and prove it works before the camera is on.

    uv run scripts/rehearse.py

The shot list's climax (docs/VIDEO.md, 1:35-2:05) is one unbroken take: the payer page shows
$520.00, apply runs, the same page is refreshed and shows $902.50 with two new named lines.

That shot could not be filmed against the committed demo invoice, and the reason is worth
stating because it would have been discovered with the camera running. `fixtures/demo-invoice-id`
has already been grown to $902.50 — it is the invoice in the README's screenshots — so the
"before" is already the "after", and the apply refuses with `409 already billed` because the
ledger correctly remembers. Both of those are the product working.

So filming needs its own invoice. This script opens one, live, at the engagement's opening
total, and leaves it sent and untouched at $520.00 with its payer URL printed. It does the
whole run first against a throwaway invoice, so "it works today" is established before anything
is recorded rather than hoped for.

What it will not touch: `fixtures/demo-invoice-id`, the committed `cassettes/` (recording stays
off), and the repository's own `data/` ledger. Each take gets its own directory under `.film/`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILM = ROOT / ".film"
ENGAGEMENT = ROOT / "fixtures" / "engagement.json"
EVENTS = ROOT / "fixtures" / "events.jsonl"


def run(*cmd: str, data: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["UNLOGGED_DATA"] = str(data)
    env["UNLOGGED_REPLAY"] = "0"
    # Never while filming, never at all here: the committed recordings are the evidence every
    # money claim rests on, and a live run used to overwrite them as a side effect.
    env["UNLOGGED_RECORD"] = ""
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr).strip()


def open_invoice(data: Path) -> tuple[str, str]:
    """A fresh sent invoice at the engagement's opening total. Returns (id, payer url)."""
    code, out = run(
        "uv", "run", "unlogged", "open-engagement", "--engagement", str(ENGAGEMENT), data=data
    )
    if code != 0:
        raise SystemExit(f"could not open an invoice:\n{out}")
    invoice_id = next(w for w in out.split() if w.startswith("INV2-"))
    url = next(w for w in out.split() if w.startswith("http"))
    return invoice_id, url


def apply_to(invoice_id: str, data: Path) -> tuple[int, str]:
    return run(
        "uv",
        "run",
        "unlogged",
        "discover",
        "--engagement",
        str(ENGAGEMENT),
        "--events",
        str(EVENTS),
        "--invoice-id",
        invoice_id,
        "--apply",
        data=data,
    )


def main() -> int:
    from unlogged.config import Settings

    if not Settings.from_env().has_paypal:
        print("No PayPal credentials. This one is live only — the whole point is a real invoice.")
        print("Put PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env and run it again.")
        return 1

    FILM.mkdir(exist_ok=True)

    # --- the rehearsal: a complete take against an invoice nobody will see ------------------
    print("Rehearsing the whole shot against a throwaway invoice first.\n")
    dry = FILM / "rehearsal"
    shutil.rmtree(dry, ignore_errors=True)
    dry.mkdir(parents=True)

    invoice_id, _url = open_invoice(dry)
    print(f"  opened  {invoice_id}")
    code, out = apply_to(invoice_id, dry)
    total = next((line for line in out.splitlines() if line.startswith("Total now")), "")
    if code != 0 or "902.50" not in total:
        print(f"\nThe shot does NOT work right now. Do not start recording.\n\n{out}")
        return 1
    print(f"  applied {total.strip()}")
    print("  the hero shot works today.\n")

    # --- the take: a fresh invoice, left at the opening total, ready to film ----------------
    take = FILM / "take"
    shutil.rmtree(take, ignore_errors=True)
    take.mkdir(parents=True)
    film_id, film_url = open_invoice(take)
    # Written down so `./demo apply` can find it. Nobody should be typing an invoice id with a
    # camera running.
    (take / "invoice-id").write_text(film_id + "\n")
    (take / "payer-url").write_text(film_url + "\n")

    print("─" * 78)
    print("READY TO FILM\n")
    print("Open this in the right-hand window and leave it open — it is the page the client")
    print("has had since day one, and the shot is worth nothing if it is reopened on camera:\n")
    print(f"  {film_url}\n")
    print("Point the service at this take, so the dashboard's own button writes to it:\n")
    print(f'  UNLOGGED_DATA=".film/take" UNLOGGED_INVOICE_ID={film_id} \\')
    print("    uv run uvicorn unlogged.web:app --port 8000\n")
    print("Then, on camera, you click Add to the live invoice. No typing at all.")
    print("If you would rather not restart the service, the terminal still works:\n")
    # Two words. The real one is four lines with two environment variables and a twenty-four
    # character invoice id, which is not something to type while talking, and is noise on
    # screen besides. `./demo` prints what it runs before it runs it, so nothing is hidden.
    print("  ./demo apply\n")
    print("Refresh the payer page. $520.00 becomes $902.50, two named lines appear, and the")
    print("URL in the address bar never changed.\n")
    print("Another take: run this script again. Each one gets its own invoice and ledger, so a")
    print("second take is not refused as already billed.")
    print("─" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
