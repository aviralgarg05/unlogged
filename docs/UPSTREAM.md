# Upstream: the documented discount path does not work

Prepared for [paypal/agent-toolkit](https://github.com/paypal/agent-toolkit). Reproduction script:
[`scripts/repro_discount_defect.py`](../scripts/repro_discount_defect.py). Run against sandbox on
2026-10-15; output below is verbatim.

## Summary

`PROMPTS.md` documents the invoice discount capability only under
`create_conditional_rules_for_invoice` with `EARLY_PAYMENT_DISCOUNT`. Both routes to that
capability fail, and one of them fails silently. An agent following the shipped guidance writes a
discount, is told it succeeded, and charges the customer the undiscounted amount.

## A. `early_payment_discount` on create is accepted and then dropped

`detail.payment_term.conditional_rules.early_payment_discount` returns **HTTP 201** and is absent
from the stored invoice. No error, no warning, and `effective_due_amount` stays `null`.

| case | result | `conditional_rules` stored | total |
|---|---|---|---|
| `DUE_ON_RECEIPT`, end date today | 201 | **false** | 100.00 |
| `NET_30`, end date today | 201 | **false** | 100.00 |
| `NET_30`, end date +7d | 201 | **false** | 100.00 |
| `DUE_ON_DATE_SPECIFIED`, end date +7d | 201 | **false** | 100.00 |

Four combinations across three payment-term types, with the discount end date both today and in
the future, so this is not a term-type or date-validity problem. The returned `payment_term`
contains only `term_type` and `due_date`.

## B. `POST /conditional-rules` returns 500

```
POST /v2/invoicing/invoices/{id}/conditional-rules -> HTTP 500
{"name":"INTERNAL_SERVER_ERROR","message":"An internal server error has occurred.","debug_id":"f1146974bd9f4"}
GET  /v2/invoicing/invoices/{id}/conditional-rules -> HTTP 200  {"invoice_id":"INV2-..."}
```

The published schema explains it. The request body is the `conditional_rules` schema, whose only
non-`links` property is `rules` — and `rules` is `readOnly: true, maxItems: 5`. **There is no
writable payload defined for this endpoint.** Verified by walking
`developer.paypal.com/api/invoicing/v2/schema.json` (557,403 bytes, 132 schemas).

## C. What does work

`amount.breakdown.discount.invoice_discount.percent` persists, and PayPal computes the money:

```
HTTP 201  total=80.00  stored={"percent": "20", "amount": {"currency_code": "USD", "value": "-20.00"}}
```

$100.00 list, 20% off, settled server-side.

## Suggested fix

Smallest useful change: point `PROMPTS.md` at `amount.breakdown.discount.invoice_discount` for
invoice-level discounts, and either remove `create_conditional_rules_for_invoice` from the
documented surface or note that it is not currently usable. A silent drop on a money field is
worse than an error, because the agent reports success.

Happy to open the PR.

## Not claimed

Sandbox only. Live behaviour untested — this account cannot send live-mode payments. Whether the
drop is a gateway-side validation gap or an intentional gate on the capability is unknown from
outside.
