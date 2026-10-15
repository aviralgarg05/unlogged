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

---

# Second report: the Server SDK has no Invoicing controller

For [APIMatic](https://www.apimatic.io/) and
[paypaldev/server-sdk-context-plugin-preview](https://github.com/paypaldev/server-sdk-context-plugin-preview).

The APIMatic-generated `paypal-server-sdk` (2.4.0, PyPI) ships six controllers:

```
o_auth_authorization, orders, payments, subscriptions, transaction_search, vault
```

There is no `invoicing` controller. Enumerated directly:

```python
import pkgutil, paypalserversdk.controllers as c
[m.name for m in pkgutil.iter_modules(c.__path__)]
```

This matters more than a missing endpoint usually would, because the Context Plugin's whole
premise is that an agent asking "how do I do X with the PayPal SDK" gets a grounded answer
rather than a remembered one. For anything invoicing-shaped the grounded answer is *you cannot
with this SDK* — and the plugin is right to say so, but an agent that does not ask will reach
for a controller that is not there.

Invoicing v2 is a large, self-serve, live surface: create, send, list, QR generation,
conditional rules, recurring series, reminders, record-payment. It is also, going by the
hackathon field, one of the most commonly reached-for parts of the platform.

**Suggested:** generate the Invoicing v2 group into the SDK, or state the covered surface in the
plugin's getting-started skill so an agent knows the boundary before it writes against it.

## What this project did instead

`src/unlogged/paypal/invoices.py` calls Invoicing v2 over `httpx`, because it has to.
`src/unlogged/paypal/settlement.py` uses the SDK for the part the SDK does cover —
`payments.get_captured_payment` and `seller_receivable_breakdown` — which answers the question
a cross-border contractor actually ends on: not "did they pay" but "how much reached me".

That division is the honest one, and it is stated in the README rather than blurred.
