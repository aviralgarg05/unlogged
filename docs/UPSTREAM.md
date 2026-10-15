# Upstream: the documented discount path does not work

Prepared for [paypal/agent-toolkit](https://github.com/paypal/agent-toolkit). Reproduction:
[`scripts/repro_discount_defect.py`](../scripts/repro_discount_defect.py). Run against sandbox on
2026-10-15; output below is verbatim.

## Summary

`PROMPTS.md` documents the invoice discount capability only under
`create_conditional_rules_for_invoice` with `EARLY_PAYMENT_DISCOUNT`. Both routes to that
capability fail, and one of them fails silently. An agent following the shipped guidance writes a
discount, is told it succeeded, and charges the customer the undiscounted amount.

## A. `early_payment_discount` is accepted and not stored

`detail.payment_term.conditional_rules.early_payment_discount` returns **HTTP 201**. The invoice
is then **sent** and **read back fresh** — not inspected in the create response, which would prove
nothing about what was persisted:

| case | create | send | in create body | in a fresh GET | total |
|---|---|---|---|---|---|
| `DUE_ON_RECEIPT`, end today | 201 | 200 | false | **false** | 100.00 |
| `NET_30`, end today | 201 | 200 | false | **false** | 100.00 |
| `NET_30`, end +7d | 201 | 200 | false | **false** | 100.00 |
| `DUE_ON_DATE_SPECIFIED`, +7d | 201 | 200 | false | **false** | 100.00 |

Four combinations across three payment-term types, with the discount end date both today and in
the future. No error at any point, and the total never moves off the list price.

## B. `POST /conditional-rules` returns 500 for every payload shape

The published schema says the request body is `conditional_rules`, whose only non-`links`
property `rules` is `readOnly: true, maxItems: 5` — which would mean no writable payload exists.
Rather than rest the report on reading a spec, the endpoint was asked, including with the exact
rule object the spec gives as its *own* worked example for the sibling `PUT` route:

| payload | result |
|---|---|
| `{"rules": [ … ]}` using the spec's own example rule | **HTTP 500** `INTERNAL_SERVER_ERROR` |
| the bare rule object | **HTTP 500** `INTERNAL_SERVER_ERROR` |
| `{"early_payment_discount": { … }}` | **HTTP 500** `INTERNAL_SERVER_ERROR` |
| `GET` on the same path | 200, body `{"invoice_id": "INV2-…"}` and nothing else |

So the endpoint is reachable and authorised, and fails on every shape its own specification
suggests. Whether the cause is the readOnly marking or something behind it, the capability is not
usable from outside.

## C. What does work

`amount.breakdown.discount.invoice_discount.percent`, verified the same way — created, sent, read
back fresh:

```
total 80.00   discount {"percent": "20", "amount": {"currency_code": "USD", "value": "-20.00"}}
```

$100.00 list, 20% off, still there after sending, with PayPal doing the arithmetic.

## Suggested fix

Smallest useful change: point `PROMPTS.md` at `amount.breakdown.discount.invoice_discount` for
invoice-level discounts, and either remove `create_conditional_rules_for_invoice` from the
documented surface or note that it is not currently usable. A silent drop on a money field is
worse than an error, because the agent reports success.

Happy to open the PR.

## Not claimed

Sandbox only; live behaviour untested, as this account cannot send live-mode payments. One
sandbox merchant. Whether the drop is gateway-side validation or an intentional gate on the
capability is not visible from outside, and this report does not guess.

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

---

# Third report: a public custom widget cannot declare `formatShape`

For [AG Grid](https://www.ag-grid.com/), on `ag-studio@3.0.0`.

`AgBaseWidgetDefinition.formatShape` is documented as *"If using AI, the shape is required, as it
uses the schema."* A custom widget therefore wants one. It cannot have one.

- The callback's parameter type is `AgFormatShapeParams`, which is an empty interface extending
  `AgStudioCommon` — i.e. `{ api, context }`. No shape builder.
- `ag-studio` exports no builder either. `Object.keys(require('ag-studio'))` returns 50 entries
  and none is shape-related; `AgShapeBuilder` is exported as a *type* only.
- Returning a plain object instead is not a graceful degradation. The engine calls
  `formatShape.parse(...)` during `hydrateWidget`, so it throws
  `TypeError: s?.formatShape?.parse is not a function` and the whole dashboard fails to render
  with `State property 'widgets' is malformed`.
- Probed at runtime, the params object does carry a `Symbol(ag.internal)` which presumably holds
  the builder — but reaching into that is not an integration, it is a dependency on a private
  field.

So the public path is: omit `formatShape`, and accept that the assistant can place and data-map
the widget but not configure its format.

**Suggested:** pass the shape builder into `AgFormatShapeParams` as `params.shape`, the way
`AgAiExecuteToolConfig.params(s)` already does for AI tools — that pattern exists and works.
Failing that, export a standalone builder, or say in the docs that `formatShape` is for built-ins.

Reproduced in `web/app/dashboard/studio/widgets/index.ts`, where the omission is commented rather
than quietly worked around.
