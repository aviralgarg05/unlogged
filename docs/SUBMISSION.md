# Devpost submission — draft

## Tagline

The work you never wrote down is the work you never got paid for.

## Inspiration

Every contractor has had the same month. You agree a scope. Then the work arrives anyway — a
"can you also just" in a Slack thread, a review comment that turns into an afternoon, a call that
overran. Some of it is inside what you agreed and some of it isn't, and the part that isn't
mostly never reaches the invoice, because writing it down at the time is the one thing nobody
does while they're doing the work.

The usual answer is a second invoice at the end, which means a new invoice number, a new approval
clock at the client's end, and a conversation nobody enjoys. So most people just eat it.

## What it does

`unlogged` watches the real work surface — Slack, Discord, PR reviews, commits, calendar — and
places each thing that happened against the engagement's own scope clauses: inside the agreement,
a request for something outside it, work actually done outside it, or noise.

The billable extras are then **itemised onto an invoice the client already has**. Same invoice
id. Same payer link they filed on day one. Same QR. Each line names where the work came from, and
PayPal emails the client that the invoice changed.

## How I built it

Python 3.12 service wrapping PayPal Invoicing v2, a Next.js dashboard on PayPal's own AG Studio
boilerplate, and an evaluation harness that scores the adjudicator against hand labels.

The mechanism took a day to find and is not in the documentation: **an invoice that has already
been sent can grow line items**, and its id, payer URL and QR survive. Verified live —
`$520.00 → $690.00 → $817.50` across two writes, every added line rendered by name on PayPal's
hosted page.

Three undocumented behaviours cost a day each and are written up in `docs/VERIFIED.md`:
`PUT` is a full-document replace and 400s on `calculation_error` if you echo back the
`amount.value` you just read; `generate-qr-code` returns `multipart/form-data`, not `image/png`;
and exactly three top-level invoice properties are readOnly, not the six commonly assumed.

## Challenges

PayPal's documented discount path does not work. `early_payment_discount` is accepted with
**HTTP 201 and then silently dropped** — tested across three payment-term types with the discount
date both today and in the future — and `POST /conditional-rules` returns **HTTP 500**, because
the only non-`links` property of its request schema is `readOnly`. The official agent toolkit's
`PROMPTS.md` documents only that path. An agent following the shipped guidance writes a discount,
is told it worked, and charges the customer full price.

Reproduction script and a suggested fix: `docs/UPSTREAM.md`.

## Accomplishments

The evaluation is the part worth pointing at. The keyword baseline — what people actually fall
back on — scores **0% precision and 0% recall** on the fixture engagement: it bills a request and
an administrative message, and misses both pieces of real out-of-scope engineering, including a PR
whose own description says "not in the original scope". That gap is the product, and it is a
number a judge can reproduce rather than a claim.

## What I learned

That a found objection is a work item, not a verdict. The first version of this printed a price
ladder on a physical sticker. One afternoon of asking actual shopkeepers killed it: they forecast
quantity well, they settle in UPI, they price by weight and bargain verbally, and their QR already
lets the payer type any amount. The mechanism survived; the problem it was pointed at did not.

## What's next

Measuring the model arm against a real past engagement — the real thread, the real commits, and
the invoice that was actually sent at the time. That invoice predates this product, so it is the
one ground truth that cannot have been shaped by it.

## Built with

`python` · `fastapi` · `pydantic` · `uv` · `openai` · `paypal-invoicing-v2` · `paypal-webhooks` ·
`nextjs` · `react` · `typescript` · `ag-grid` · `ag-studio`

## AI tools used, and how

- **gpt-6.1-sol** (OpenAI Responses API, strict JSON schema, function calling) — the adjudicator.
  Decides whether a piece of work falls inside the agreed scope, and must quote the clause it
  relied on and the span of text that decided it. A verdict that cannot cite its own evidence is
  rejected.
- **gpt-5.4-mini** — the AG Studio dashboard assistant, via the boilerplate's shipped adapter.
- The OpenAI key is read server-side only. It is never sent to the browser, and the one mutating
  tool is declared client-side but executed on the server for that reason.

## Try it

```bash
git clone https://github.com/aviralgarg05/unlogged && cd unlogged
uv sync --extra dev && uv run pytest -q
```

No PayPal account, no OpenAI key, no licence key. Recorded sandbox exchanges replay from
`cassettes/`, and with no key the project runs on the keyword baseline — which is the evaluation's
ablation arm, not a stub.
