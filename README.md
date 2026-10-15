# unlogged

[![ci](https://github.com/aviralgarg05/unlogged/actions/workflows/ci.yml/badge.svg)](https://github.com/aviralgarg05/unlogged/actions/workflows/ci.yml)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

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
uv run scripts/verify.py               # checks every claim in this README
```

That script is the short version of everything below: it runs the tests, reproduces the
evaluation to the cent, replays the full apply flow from recorded PayPal exchanges, and checks
the submission requirements (LICENSE present, no key tracked, no key anywhere in the repo).
Thirteen checks, no credentials, about twenty seconds.

With sandbox credentials, `uv run scripts/verify.py --live` also re-proves the central claim
against PayPal on the day you run it — it creates a real invoice, grows it, and prints the
payer URL so you can open it yourself. A date in a README is worth less than a command.

Or run the pieces directly:

```bash
uv run pytest -q                       # 55 tests, no credentials needed
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

### Running it with your own keys

Nothing below is required to evaluate the project — the commands above work with none of it.
Both files are gitignored; no key is ever committed, and none appears in the git history.

**The Python service** reads `.env` (copy `.env.example`):

| Variable | What it does |
|---|---|
| `OPENAI_API_KEY` | Switches the adjudicator from the keyword baseline to `gpt-6.1-sol`. The CLI, `/health` and the dashboard all follow automatically; there is no other change to make. |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | A sandbox REST app from developer.paypal.com. |
| `UNLOGGED_REPLAY` | `1` replays recorded responses (default), `0` calls the live sandbox. |

**The dashboard** reads `web/.env.local`:

| Variable | What it does |
|---|---|
| `AG_STUDIO_OPENAI_API_KEY` | Enables the AG Studio assistant. Read server-side only — there is deliberately no `NEXT_PUBLIC_` variable for it, so it is never inlined into the browser bundle. Falls back to `OPENAI_API_KEY`. |
| `OPENAI_MODELS` | Comma-separated. Two or more turns on the model picker in the chat panel. |
| `UNLOGGED_API` | Where the Python service is listening. Defaults to `http://127.0.0.1:8000`. |

With a key set, confirm it took effect:

```bash
curl -s localhost:8000/health    # "adjudicator" flips to gpt-6.1-sol
```

### The dashboard

One command, both halves, still no credentials:

```bash
docker compose up        # dashboard on :3000/dashboard, API on :8000
```

Or without Docker:

```bash
uv run uvicorn unlogged.web:app --port 8000            # one shell
cd web && npm install && npm run build && npm start    # another
```

Built on PayPal's own [AG Studio boilerplate](https://github.com/paypaldev/hackathon-paypal-ag-grid-boilerplate),
with one deliberate departure. The boilerplate hands AG Studio a fully-materialised array and
lets the engine filter, sort and page it in the browser. `app/dashboard/studio/data.ts` instead
declares `capabilities: { pagination, filter, sort }`, so the engine sends `paging`, the applied
filter tree and the sort order down to `getData`, trusts the returned window as-is, and never
re-filters locally. **The rows stay in the Python service.**

Four more things the surveyed entries leave untouched. A sixth agent owns the decision this
product exists to make and hands layout work to AG's built-in five through `delegateTo`.
`defaultToolCalls` seeds it with the scope, the adjudications and the changes already made
*before its first turn*, so its opening reply is a decision rather than a question. The one
tool that moves money is `kind: 'server'` — Studio advertises the schema and never runs it, so
the PayPal write happens in our own route and the credential never enters the bundle. And an
`AgAiTelemetryObserver` reads `api.getState()` synchronously in-loop, where it sees the exact
post-mutation state a call produced, then batches to the backend for scoring.

No AG Studio licence key. `validateLicense()` only ever sets a watermark message — no branch
disables a feature — and `isDisplayWatermark()` returns false on localhost. A trial key is
strictly worse than none, because a trial can expire and nothing here can.

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

## APIMatic, and the division of labour it forced

The APIMatic-generated [`paypal-server-sdk`](https://pypi.org/project/paypal-server-sdk/) ships
six controllers — oauth, orders, payments, subscriptions, transaction search, vault — and **none
of them is Invoicing**. Everything this product does to an invoice therefore goes through
`paypal/invoices.py` on `httpx`, because there is no alternative.

The SDK is used for the one part it genuinely serves, and it closes the loop the product opens.
A contractor's question does not end at *did the client pay*; for cross-border work it ends at
*how much reached me*, and the difference is PayPal's cross-border and conversion cut.
`payments.get_captured_payment` returns `seller_receivable_breakdown` — gross, fee, net, and the
exchange rate PayPal used — which is PayPal stating its own arithmetic rather than us estimating it.

The missing controller is reported in [`docs/UPSTREAM.md`](docs/UPSTREAM.md) rather than worked
around quietly, because the Context Plugin's premise is that an agent gets a grounded answer about
what the SDK can do — and for anything invoicing-shaped, the grounded answer is that it cannot.

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
| Mechanism verified live | ✅ 2026-10-15, `$520 → $690 → $817.50` |
| Invoice engine | ✅ live sandbox, end to end |
| Webhooks + signature verification | ✅ |
| HTTP API + `/health` | ✅ |
| Keyword baseline (the ablation arm) | ✅ scores 0% precision, 0% recall |
| Evaluation harness + JUnit | ✅ |
| AG Studio dashboard | ✅ async data source, server-side paging |
| Keyless replay path | ✅ full flow runs with no credentials |
| AI harness: custom agent, server tool, telemetry | ✅ built, unexercised without a key |
| APIMatic SDK: settlement breakdown | ✅ `payments.get_captured_payment` |
| Docker Compose, Render blueprint | ✅ API image built and verified |
| Tests | ✅ 55 Python (incl. a property test on the money path), 4 TypeScript |
| Model adjudication | ⏳ awaiting API key |
| Evaluation against a real past engagement | ⏳ needs a real thread |

## How this is judged, and where to check each claim

Five equally weighted criteria. For each one, the screen that shows it and the file that
implements it, so nothing has to be taken on trust.

| Criterion | See it here | Implemented in |
|---|---|---|
| **Technological Implementation** | `uv run scripts/repro_discount_defect.py` — PayPal's documented discount path accepted with 201 and silently dropped, four ways | [`paypal/invoices.py`](src/unlogged/paypal/invoices.py), [`docs/UPSTREAM.md`](docs/UPSTREAM.md) |
| **Design** | `/dashboard` — three pages, rows fetched a page at a time, never materialised in the browser | [`studio/data.ts`](web/app/dashboard/studio/data.ts) |
| **Potential Impact** | `uv run unlogged evaluate …` — $425 of real work the naive pass leaves off the bill | [`eval/harness.py`](src/unlogged/eval/harness.py), [`fixtures/gold.jsonl`](fixtures/gold.jsonl) |
| **Innovation** | The client's bookmarked PayPal page gaining named line items, same invoice id, same QR | [`Invoices.add_items`](src/unlogged/paypal/invoices.py) |
| **Presentation** | [`docs/VIDEO.md`](docs/VIDEO.md) — the shot list, and the rule that every claim lands on PayPal's own page | — |

**What is real, what is simulated, and what is not yet true:** [`docs/HONESTY.md`](docs/HONESTY.md).
Read that before the rest. It says plainly that no model number has been published yet, that the
fixture thread was authored for this repo, and why that matters.

## Licence

MIT — see [LICENSE](LICENSE).
