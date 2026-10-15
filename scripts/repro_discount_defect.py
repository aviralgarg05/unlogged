# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Reproduction: PayPal Invoicing v2 accepts an early-payment discount and silently drops it.

    export PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=...
    uv run scripts/repro_discount_defect.py

What this shows, against api-m.sandbox.paypal.com:

  A. `detail.payment_term.conditional_rules.early_payment_discount` is accepted on create with
     HTTP 201 and is then absent from the stored invoice. No error, no warning. Tried across
     three payment term types and with the discount end date both today and in the future, so
     it is not a term-type or date-validity problem.
  B. `POST /v2/invoicing/invoices/{id}/conditional-rules` returns HTTP 500. The published
     schema explains why: the only non-`links` property of its request body, `rules`, is
     marked `readOnly`, so there is no writable payload to send.
  C. The field that does work is `amount.breakdown.discount.invoice_discount.percent`.

Why it matters beyond the API: the official agent toolkit's PROMPTS.md documents the discount
capability only under `create_conditional_rules_for_invoice` / EARLY_PAYMENT_DISCOUNT — the path
in A and B. An agent following the shipped guidance writes a discount, is told it succeeded, and
charges the customer the undiscounted amount.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

import httpx

BASE = "https://api-m.sandbox.paypal.com"
TODAY = date.today().isoformat()
SOON = (date.today() + timedelta(days=7)).isoformat()


def token(c: httpx.Client) -> str:
    cid, sec = os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.")
    r = c.post(
        f"{BASE}/v1/oauth2/token",
        auth=(cid, sec),
        data={"grant_type": "client_credentials"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def invoice(term: dict, end_date: str) -> dict:
    return {
        "detail": {
            "currency_code": "USD",
            "invoice_date": TODAY,
            "reference": "repro",
            "payment_term": {
                **term,
                "conditional_rules": {
                    "early_payment_discount": {"percent": "20", "discount_end_date": end_date}
                },
            },
        },
        "invoicer": {"business_name": "Repro"},
        "items": [
            {
                "name": "Item",
                "quantity": "1",
                "unit_amount": {"currency_code": "USD", "value": "100.00"},
                "unit_of_measure": "QUANTITY",
            }
        ],
    }


def main() -> int:
    with httpx.Client(timeout=60.0) as c:
        h = {
            "Authorization": f"Bearer {token(c)}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        print("A. early_payment_discount on create — accepted, then absent\n")
        cases = [
            ("DUE_ON_RECEIPT, end date today", {"term_type": "DUE_ON_RECEIPT"}, TODAY),
            ("NET_30, end date today", {"term_type": "NET_30"}, TODAY),
            ("NET_30, end date +7d", {"term_type": "NET_30"}, SOON),
            (
                "DUE_ON_DATE_SPECIFIED, end date +7d",
                {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": SOON},
                SOON,
            ),
        ]
        first_id = None
        for label, term, end in cases:
            r = c.post(f"{BASE}/v2/invoicing/invoices", headers=h, json=invoice(term, end))
            if r.status_code != 201:
                print(f"   {label:38} HTTP {r.status_code} {r.text[:120]}")
                continue
            body = r.json()
            first_id = first_id or body["id"]
            stored = body.get("detail", {}).get("payment_term", {})
            survived = "conditional_rules" in stored
            total = (body.get("amount") or {}).get("value")
            eff = (body.get("effective_due_amount") or {}).get("value")
            print(
                f"   {label:38} HTTP 201  conditional_rules stored: {survived}  "
                f"total={total}  effective_due_amount={eff}"
            )
            print(f"   {'':38} payment_term returned: {json.dumps(stored)}")

        print("\nB. POST /conditional-rules\n")
        r = c.post(
            f"{BASE}/v2/invoicing/invoices/{first_id}/conditional-rules",
            headers=h,
            json={"early_payment_discount": {"percent": "10", "discount_end_date": TODAY}},
        )
        print(f"   POST /v2/invoicing/invoices/{{id}}/conditional-rules -> HTTP {r.status_code}")
        print(f"   {r.text[:220]}")
        r = c.get(f"{BASE}/v2/invoicing/invoices/{first_id}/conditional-rules", headers=h)
        print(f"   GET  same path -> HTTP {r.status_code}  {r.text[:160]}")

        print("\nC. The field that does work\n")
        body = {
            "detail": {"currency_code": "USD", "invoice_date": TODAY, "reference": "repro-works"},
            "invoicer": {"business_name": "Repro"},
            "items": [
                {
                    "name": "Item",
                    "quantity": "1",
                    "unit_amount": {"currency_code": "USD", "value": "100.00"},
                    "unit_of_measure": "QUANTITY",
                }
            ],
            "amount": {
                "currency_code": "USD",
                "breakdown": {"discount": {"invoice_discount": {"percent": "20"}}},
            },
        }
        r = c.post(f"{BASE}/v2/invoicing/invoices", headers=h, json=body)
        got = r.json()
        disc = (((got.get("amount") or {}).get("breakdown") or {}).get("discount") or {}).get(
            "invoice_discount", {}
        )
        print(
            f"   amount.breakdown.discount.invoice_discount -> HTTP {r.status_code}  "
            f"total={(got.get('amount') or {}).get('value')}  "
            f"stored={json.dumps(disc)}"
        )
        print("\n   $100.00 list, 20% off, PayPal computed the money itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
