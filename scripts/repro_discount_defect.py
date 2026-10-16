# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Reproduction: PayPal Invoicing v2 accepts an early-payment discount and does not store it.

    export PAYPAL_CLIENT_ID=... PAYPAL_CLIENT_SECRET=...
    uv run scripts/repro_discount_defect.py

Each claim is checked against a FRESH GET of the stored invoice after sending it, not against
the create response. That distinction matters: a representation echoed back on create would
prove nothing about what PayPal persisted, and an earlier version of this script made exactly
that mistake.

The `rules` array is also POSTed for real rather than ruled out from the schema. It is marked
`readOnly` in the published spec, but a spec can be wrong about its own endpoint, so the
endpoint gets asked.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

import httpx

from unlogged.paypal.invoices import today

BASE = "https://api-m.sandbox.paypal.com"
TODAY = today().isoformat()
SOON = (today() + timedelta(days=7)).isoformat()

# Exactly the shape the published spec gives as its own worked example for
# PUT /v2/invoicing/invoices/{id}/conditional-rules/{conditional_rule_id}.
RULE = {
    "conditional_rule_type": "EARLY_PAYMENT_DISCOUNT",
    "conditional_rule_value_type": "PERCENT",
    "conditional_rule_value": "10",
    "rule_expiry_terms": {
        "rule_expiry_condition": "SEVEN_DAYS_AFTER_ISSUE_DATE",
        "condition_rule_end_date": SOON,
    },
}


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


def invoice_body(term: dict, end_date: str) -> dict:
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


def stored_rules(inv: dict) -> dict | None:
    return inv.get("detail", {}).get("payment_term", {}).get("conditional_rules")


def main() -> int:
    with httpx.Client(timeout=60.0) as c:
        h = {
            "Authorization": f"Bearer {token(c)}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        print("A. early_payment_discount on create — checked against a fresh GET after sending\n")
        cases = [
            ("DUE_ON_RECEIPT, end today", {"term_type": "DUE_ON_RECEIPT"}, TODAY),
            ("NET_30, end today", {"term_type": "NET_30"}, TODAY),
            ("NET_30, end +7d", {"term_type": "NET_30"}, SOON),
            (
                "DUE_ON_DATE_SPECIFIED, +7d",
                {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": SOON},
                SOON,
            ),
        ]
        first_id = None
        for label, term, end in cases:
            r = c.post(f"{BASE}/v2/invoicing/invoices", headers=h, json=invoice_body(term, end))
            if r.status_code != 201:
                print(f"   {label:28} create HTTP {r.status_code} {r.text[:90]}")
                continue
            iid = r.json()["id"]
            first_id = first_id or iid
            on_create = stored_rules(r.json()) is not None

            # Send it, then read it back fresh. This is the step that makes the claim stand up.
            sent = c.post(
                f"{BASE}/v2/invoicing/invoices/{iid}/send",
                headers=h,
                json={"send_to_recipient": False, "send_to_invoicer": False},
            )
            fresh = c.get(f"{BASE}/v2/invoicing/invoices/{iid}", headers=h).json()
            after = stored_rules(fresh)
            print(
                f"   {label:28} 201 | send {sent.status_code} | in create body: {on_create} "
                f"| in fresh GET: {after is not None} | status {fresh.get('status')} "
                f"| total {(fresh.get('amount') or {}).get('value')}"
            )

        print("\nB. POST /conditional-rules, asked rather than assumed\n")
        attempts = [
            ("rules array (the spec's own rule shape)", {"rules": [RULE]}),
            ("bare rule object", RULE),
            (
                "early_payment_discount shorthand",
                {"early_payment_discount": {"percent": "10", "discount_end_date": TODAY}},
            ),
        ]
        for label, body in attempts:
            r = c.post(
                f"{BASE}/v2/invoicing/invoices/{first_id}/conditional-rules", headers=h, json=body
            )
            if r.headers.get("content-type", "").startswith("application/json"):
                detail = r.json().get("name", "") or r.text[:60]
            else:
                detail = r.text[:60]
            print(f"   {label:42} HTTP {r.status_code}  {detail[:46]}")

        r = c.get(f"{BASE}/v2/invoicing/invoices/{first_id}/conditional-rules", headers=h)
        print(f"   {'GET /conditional-rules':42} HTTP {r.status_code}  {r.text[:46]}")

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
        iid = r.json()["id"]
        c.post(
            f"{BASE}/v2/invoicing/invoices/{iid}/send",
            headers=h,
            json={"send_to_recipient": False, "send_to_invoicer": False},
        )
        fresh = c.get(f"{BASE}/v2/invoicing/invoices/{iid}", headers=h).json()
        disc = (((fresh.get("amount") or {}).get("breakdown") or {}).get("discount") or {}).get(
            "invoice_discount", {}
        )
        print(
            f"   amount.breakdown.discount.invoice_discount  create {r.status_code} | "
            f"after a fresh GET: {json.dumps(disc)} | total "
            f"{(fresh.get('amount') or {}).get('value')}"
        )
        print("\n   $100.00 list, 20% off, still there after sending. PayPal did the arithmetic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
