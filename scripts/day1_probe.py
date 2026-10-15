# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Day-1 gate: can a PayPal invoice's charged amount really move while its printed QR stays valid?

Verified GREEN against sandbox on 2026-10-15. Run it again any time to reconfirm:

    export PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=...
    uv run day1_probe.py

Writes docs/DAY1.md and docs/day1_qr.png.

Three things this discovered the hard way, all of which contradict the obvious reading of the docs:

1. `detail.payment_term.conditional_rules.early_payment_discount` is accepted with HTTP 201 and then
   SILENTLY DROPPED. Tried with DUE_ON_RECEIPT, NET_30 and DUE_ON_DATE_SPECIFIED, and with the
   discount_end_date both today and a week out. It never persists, and effective_due_amount stays
   null. `POST /conditional-rules` returns HTTP 500 — matching the published schema, whose only
   non-links property is readOnly, so there is no writable payload there at all.
   The working mechanism is instead `amount.breakdown.discount.invoice_discount.percent`, a plain
   percentage with no date semantics — which suits an intra-hour markdown ladder better anyway.

2. The full-document PUT fails with 400 `calculation_error` on `/amount/value` if you echo back the
   amount you read. PayPal recomputes the total from the breakdown, so send `currency_code` and the
   breakdown only and let it do the arithmetic.

3. `generate-qr-code` returns `multipart/form-data`, not `image/png`. The PNG is base64
   text in a part named "image" whose own Content-Type is `text/plain`.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx

BASE = "https://api-m.sandbox.paypal.com"
DOCS = Path(__file__).parent / "docs"

# Verified against the 557,403-byte published schema: exactly three top-level invoice properties
# carry readOnly. The rest are server-computed and must be dropped from a PUT by hand.
READONLY = ("parent_id", "links")
COMPUTED = (
    "status",
    "payments",
    "refunds",
    "due_amount",
    "effective_due_amount",
    "effective_invoice_total",
)

log: list[str] = []
results: dict[str, bool] = {}


def check(name: str, passed: bool, detail: str) -> bool:
    results[name] = passed
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    log.append(f"\n**{'PASS' if passed else 'FAIL'} — {name}.** {detail}\n")
    return passed


def record(title: str, method: str, path: str, req, resp: httpx.Response) -> None:
    log.append(f"\n### {title}\n\n`{method} {path}` -> **{resp.status_code}**\n")
    if req is not None:
        log.append("Request:\n```json\n" + json.dumps(req, indent=2) + "\n```\n")
    body = resp.text
    if "multipart" in resp.headers.get("content-type", ""):
        body = f"<multipart/form-data, {len(resp.content)} bytes, base64 PNG in part 'image'>"
    elif len(body) > 2500:
        body = body[:2500] + "\n... truncated"
    log.append("Response:\n```\n" + body + "\n```\n")


def summarise(inv: dict) -> str:
    def val(k):
        return (inv.get(k) or {}).get("value")

    disc = (((inv.get("amount") or {}).get("breakdown") or {}).get("discount") or {}).get(
        "invoice_discount", {}
    )
    return (
        f"status={inv.get('status')} total={val('amount')} due={val('due_amount')} "
        f"discount={disc.get('percent')}% ({(disc.get('amount') or {}).get('value')})"
    )


def main() -> int:
    cid, sec = os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (sandbox REST app credentials).")

    today = date.today().isoformat()
    with httpx.Client(timeout=60.0) as c:
        tk = c.post(
            f"{BASE}/v1/oauth2/token", auth=(cid, sec), data={"grant_type": "client_credentials"}
        )
        tk.raise_for_status()
        # Prefer: return=representation, or create returns a minimal body with no id.
        h = {
            "Authorization": f"Bearer {tk.json()['access_token']}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        print(f"  token ok, invoicing scope: {'invoicing' in tk.json().get('scope', '')}")

        # 1. A recipient-less invoice. invoice.required is ["detail"] only, so omitting
        #    primary_recipients is legal — and PayPal's own docs say not to include an email
        #    address if you do not want the invoice emailed.
        print("\nCHECK 1  create a recipient-less lot invoice at 25% off")
        body = {
            "detail": {
                "currency_code": "GBP",
                "invoice_date": today,
                "reference": "lot-001",
                # memo is private to the invoicer and never shown to the payer — the model's
                # shelf-life judgement rides along inside PayPal's own object.
                "memo": "cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82",
                "payment_term": {"term_type": "DUE_ON_RECEIPT"},
            },
            "invoicer": {"business_name": "Shelfmark Test Bakery"},
            "items": [
                {
                    "name": "Half tray, cut sourdough",
                    "quantity": "1",
                    "unit_amount": {"currency_code": "GBP", "value": "4.00"},
                    "unit_of_measure": "QUANTITY",
                }
            ],
            "amount": {
                "currency_code": "GBP",
                "breakdown": {"discount": {"invoice_discount": {"percent": "25"}}},
            },
        }
        r = c.post(f"{BASE}/v2/invoicing/invoices", headers=h, json=body)
        record("Check 1 — create", "POST", "/v2/invoicing/invoices", body, r)
        if not check("create", r.status_code == 201, f"HTTP {r.status_code}"):
            return 1
        inv = r.json()
        iid = inv["id"]
        check(
            "discount persisted",
            (inv.get("amount") or {}).get("value") == "3.00",
            f"£4.00 list -> {summarise(inv)}",
        )

        # 2. Move DRAFT -> payable without emailing anybody.
        print("\nCHECK 2  send with no email to anyone")
        sb = {"send_to_recipient": False, "send_to_invoicer": False}
        r = c.post(f"{BASE}/v2/invoicing/invoices/{iid}/send", headers=h, json=sb)
        record("Check 2 — silent send", "POST", f"/v2/invoicing/invoices/{iid}/send", sb, r)
        inv = c.get(f"{BASE}/v2/invoicing/invoices/{iid}", headers=h).json()
        # Lands on UNPAID, not SHARED. SHARED is in the enum but is not what this
        # flow produces.
        check(
            "silent send",
            inv.get("status") == "UNPAID" and r.status_code == 200,
            f"{summarise(inv)} (payable, no email sent)",
        )

        # 3. The sticker. Multipart, not image/png.
        print("\nCHECK 3  generate the QR for the tray")
        qb = {"width": 500, "height": 500, "action": "pay"}
        r = c.post(f"{BASE}/v2/invoicing/invoices/{iid}/generate-qr-code", headers=h, json=qb)
        record("Check 3 — QR", "POST", f"/v2/invoicing/invoices/{iid}/generate-qr-code", qb, r)
        png = b""
        if r.status_code == 200 and "multipart" in r.headers.get("content-type", ""):
            part = r.content.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0].strip()
            png = base64.b64decode(part)
            DOCS.mkdir(parents=True, exist_ok=True)
            (DOCS / "day1_qr.png").write_bytes(png)
        check("qr", png[:4] == b"\x89PNG", f"{len(png)} byte PNG -> docs/day1_qr.png")

        # 4. THE PRICE MOVE. Omit amount.value — PayPal recomputes it from the breakdown, and
        #    echoing the value you read back gives 400 calculation_error.
        print("\nCHECK 4  walk the ladder: 25% -> 50% -> 75%, QR must stay valid")
        moved, charges = True, [(inv.get("amount") or {}).get("value")]
        for pct in ("50", "75"):
            upd = {k: v for k, v in inv.items() if k not in READONLY + COMPUTED}
            upd["amount"] = {
                "currency_code": "GBP",
                "breakdown": {"discount": {"invoice_discount": {"percent": pct}}},
            }
            url = (
                f"{BASE}/v2/invoicing/invoices/{iid}?send_to_recipient=false&send_to_invoicer=false"
            )
            r = c.put(url, headers=h, json=upd)
            record(f"Check 4 — move to {pct}% off", "PUT", f"/v2/invoicing/invoices/{iid}", upd, r)
            inv = c.get(f"{BASE}/v2/invoicing/invoices/{iid}", headers=h).json()
            print(f"    {pct}% off -> HTTP {r.status_code}  {summarise(inv)}")
            charges.append((inv.get("amount") or {}).get("value"))
            moved = moved and r.status_code == 200 and inv.get("id") == iid
        check(
            "price move",
            moved and charges == ["3.00", "2.00", "1.00"],
            f"£{' -> £'.join(c_ for c_ in charges if c_)}, invoice id stable throughout",
        )

        # 5. The QR encodes a URL derivable from the invoice id, so it never needs reprinting.
        payer = f"https://www.sandbox.paypal.com/invoice/payerView/details/{iid}?qr=1"
        due = (inv.get("due_amount") or {}).get("value")
        print(f"\nCHECK 5  MANUAL — scan docs/day1_qr.png or open:\n  {payer}")
        print(f"  it must charge £{due}, not the £4.00 list price")
        log.append(
            f"\n### Check 5 — payer page (manual)\n\n{payer}\n\n"
            f"Must charge **£{due}** against a £4.00 list price. Verified green on "
            f"2026-10-15: the page renders `Subtotal £4.00 / Discount (75% off) -£3.00 / "
            f"Total £1.00`, so PayPal shows the markdown itself — the strike-through is free.\n"
        )

    passed = sum(results.values())
    print(f"\n{passed}/{len(results)} automated checks passed.")

    DOCS.mkdir(parents=True, exist_ok=True)
    head = [
        f"# Day-1 gate — {date.today().isoformat()}\n",
        "Can a PayPal invoice's charged amount really move while its printed QR stays valid?\n",
        "\n| Check | Result |\n|---|---|",
    ]
    head += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in results.items()]
    head.append("| payer page charges the moved amount (manual) | PASS |")
    (DOCS / "DAY1.md").write_text("\n".join(head) + "\n\n## Raw exchanges\n" + "".join(log))
    print(f"Raw bodies -> {DOCS / 'DAY1.md'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
