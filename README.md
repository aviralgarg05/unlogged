# unlogged

**The work you never wrote down is the work you never got paid for.**

You agree a scope. Then the work arrives anyway — in a Slack thread, a PR review, a call
that overran. Some of it is inside what you agreed and some of it isn't, and the part that
isn't mostly never reaches the invoice, because writing it down at the time is the one
thing nobody does.

`unlogged` watches the real work surface, decides which side of the agreed line each piece
falls on, and **itemises the billable extras onto an invoice the client already has** —
same invoice id, same link they filed on day one, each line naming where the work came
from, rendered by PayPal on PayPal's own page.

> ⚠️ Work in progress. Private during development; this repo goes public before submission.

---

## For judges (2 minutes)

```bash
git clone https://github.com/aviralgarg05/unlogged && cd unlogged
uv sync --extra dev
uv run pytest -q                       # 17 tests, no credentials needed
uv run unlogged discover \
  --engagement fixtures/engagement.json \
  --events fixtures/events.jsonl \
  --invoice-id INV2-DEMO
```

No PayPal account, no OpenAI key, no licence key. Recorded PayPal exchanges replay from
`cassettes/`, and with no `OPENAI_API_KEY` the project falls back to the keyword baseline —
which is not a stub but **the evaluation's ablation arm**, the thing the model has to beat.

Run it and you will see the baseline get one decision right, bill a request for *a copy of
last month's invoice*, and miss all three pieces of real out-of-scope engineering — including
a PR whose own description says "not in the original scope". That gap is the product.

---

## The mechanism

An invoice that has already been sent can **grow line items**. The invoice id, and therefore
the payer-view URL and the QR the client filed, stay valid.

Verified live against the PayPal sandbox on 2026-10-15 — `$520.00 → $690.00 → $817.50`
across two writes, id stable, every discovered item named on the client's page:

```
Checkout page — agreed scope                        $520.00   8hrs x $65.00
Retry logic on checkout (slack 02 Oct)              $170.00   2hrs x $85.00
Review thread fixes (github 06 Oct)                 $127.50   1.5hrs x $85.00
                                          Subtotal  $817.50
                                             Total  $817.50
```

The client is notified by PayPal itself on every change — `send_to_recipient=true` on the
update is PayPal's own machinery, not something invented here. The agreed scope and cap are
written into `detail.note`, which PayPal renders to the payer as "Note from seller".

**Three things this cost a day to find out.** They are written down in `docs/VERIFIED.md`
with the raw exchanges, because the published docs do not say any of them:

1. `PUT /v2/invoicing/invoices/{id}` is a **full-document replace**. Echo back the
   `amount.value` you just read and you get `400 calculation_error`. Send the currency and
   the breakdown and let PayPal do the arithmetic.
2. `generate-qr-code` returns **`multipart/form-data`**, not `image/png`. The PNG is base64
   text in a part named `image` whose own Content-Type is `text/plain`.
3. Exactly **three** top-level invoice properties are readOnly — `id`, `parent_id`, `links`.
   `status`, `due_amount` and `gratuity` are not, contrary to folklore.

**And one upstream defect.** PayPal's documented discount path,
`detail.payment_term.conditional_rules.early_payment_discount`, is accepted with HTTP 201
and then **silently dropped** — tested with `DUE_ON_RECEIPT`, `NET_30` and
`DUE_ON_DATE_SPECIFIED`, with discount dates both today and future.
`POST /conditional-rules` returns **HTTP 500**, because the only non-`links` property of its
request schema is `readOnly`. The official agent toolkit's `PROMPTS.md` documents only that
dead path. Reproduction script and an upstream report are in `docs/`.

## Why the model is not optional

Deciding whether *"can you also just add the retry"* sits inside *"build the checkout page"*
is a judgement about two pieces of prose, against a rate card that is itself prose. There is
no column to join on. Being asked politely does not make something billable, and arriving
with no request at all does not make it unbillable — which is precisely where keyword
triage, the thing people actually fall back on today, breaks.

Every verdict must quote the clause it relied on and the span of the event that decided it.
A verdict that cannot cite its own evidence is not auditable, and this bills a real person.

## Why PayPal

The user is a contractor in India, Pakistan, Nigeria, Brazil or Poland billing a client in
the US, UK or EU. Inbound cross-border is exactly what PayPal does here, and PayPal hosts the
payer page, the itemisation and the QR, so the contractor ships none of it.

It also answers the obvious question directly: a static UPI QR is payee-only and the **payer**
types any amount — no itemisation, no agreed ceiling, no record of what was agreed, and no
cross-border reach. This is the inverse.

## Layout

```
src/unlogged/
  config.py              settings; replay is the default so it runs with no credentials
  paypal/client.py       OAuth2, PayPal-Request-Id, cassette replay
  paypal/invoices.py     create, silent send, grow items, QR, payer URL
  scope/models.py        Engagement, ScopeClause, WorkEvent, Verdict
  scope/baseline.py      keyword triage — the ablation arm
  scope/adjudicate.py    gpt-6.1-sol on the Responses API, strict JSON schema
  ledger.py              append-only record of every change to a live invoice
  cli.py                 open-engagement / discover / show
```

## Status

| | |
|---|---|
| Mechanism verified live | ✅ 2026-10-15 |
| Invoice engine | ✅ |
| Keyword baseline + tests | ✅ 17 passing |
| Model adjudication | ⏳ awaiting API key |
| Evaluation vs. a real past engagement | ⏳ |
| AG Studio dashboard | ⏳ |

## Licence

MIT — see [LICENSE](LICENSE).
