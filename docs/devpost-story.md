# Devpost — "About the project"

Paste everything between the rules into the **About the project** box. It is Markdown, which
Devpost renders. Nothing below needs editing except the video link once it is up.

---

## Inspiration

Every contractor has had the same month. You agree a scope. Then the work arrives anyway — a
"can you also just" in a Slack thread, a review comment that turns into an afternoon, a call
that overran. Some of it is inside what you agreed and some of it isn't, and the part that isn't
mostly never reaches the invoice, because writing it down *while you are doing it* is the one
thing nobody does.

The usual answer is a second invoice at the end: a new invoice number, a new approval clock at
the client's end, and a conversation nobody enjoys. So most people just eat it. I did, for an
afternoon of retry logic that my own agreement explicitly excluded.

## What it does

An engagement has **one** PayPal invoice, and the client keeps that link from day one.

`unlogged` reads the real work surface — Slack, PR reviews, commits, calendar — and places each
event against the engagement's own scope clauses: inside the agreement, a request for something
outside it, work actually done outside it, or noise. Every verdict must **name the clause it
relied on and quote the span of text that decided it**; one that cannot is refused before it can
reach a bill.

The billable extras are then **itemised onto the invoice the client already has**. Same invoice
id. Same payer link. Same QR. Each line names where the work came from, and PayPal emails the
client that it changed.

**See it:** [the live sandbox invoice](https://www.sandbox.paypal.com/invoice/payerView/details/INV2-DP6S-XFGQ-67JW-TMQL?qr=1) —
`$520.00` of agreed scope plus two discovered lines, `$902.50`, each naming the PR it came from.

## How I built it

A Python 3.12 service over PayPal Invoicing v2, a Next.js dashboard on PayPal's own AG Studio
boilerplate, and an evaluation harness that scores the adjudicator against hand labels.

The mechanism took a day to find and is in no documentation: **an already-sent invoice can grow
line items**, and its id, payer URL and QR survive. That last part is the claim the whole product
rests on, and PayPal's reference says nothing about it either way — so the live check captures
the payer link and the QR *before* the write and compares after. The link is unchanged and the
QR comes back **byte-identical**.

Two pieces do the work, and the division is deliberate:

- **PayPal Invoicing v2**, called over `httpx`, because the generated Server SDK ships no
  invoicing controller at all. `PUT` is a full-document replace, so the current invoice is read,
  the readOnly and server-computed fields are dropped, and `amount` is reduced to its currency so
  PayPal recomputes the total itself.
- **gpt-6.1-sol** as the adjudicator, over the Responses API with a strict JSON schema. It is
  given the clauses and the events and must cite one and quote the other. The grounding check
  refuses a verdict citing a clause the engagement does not have, or quoting words the event does
  not contain.

Everything runs with **no credentials**. 305 recorded PayPal exchanges and every model verdict
are committed, so `uv run scripts/verify.py` reproduces the full apply flow — ending at
`Total now USD 902.50` — on a clean clone with no PayPal account and no OpenAI key.

## Challenges I ran into

**PayPal's documented discount path does not work.** `early_payment_discount` is accepted with
**HTTP 201 and then silently dropped** — four term/date combinations, created, sent and re-read
fresh, absent every time, the total never moving off the list price. `POST /conditional-rules`
returns **HTTP 500** for every payload shape its own specification suggests. The official agent
toolkit's `PROMPTS.md` documents only that path, so an agent following the shipped guidance
writes a discount, is told it succeeded, and charges the customer full price.

**`PayPal-Request-Id` is ignored on an invoice `PUT`.** The identical write sent twice under one
key took a sandbox invoice from `$225.00` to `$250.00`. The resource carries no ETag and the
update accepts no `If-Match` either. So the guard here is an append-only ledger under a file
lock, written *before* the call — a guard recorded afterwards does not exist during the window it
has to cover — and `unlogged reconcile` exists to find the divergence the API cannot prevent.

**A timezone bug, in a product for cross-border contractors.** `date.today()` is local. East of
UTC it runs a day ahead for the first hours of the morning, and PayPal treats a future
`invoice_date` as a *scheduled* invoice: the send never reaches `UNPAID`, and without a recipient
it is refused with `MISSING_RECIPIENT_EMAIL` — an error naming the one field that is not the
cause. A working integration looked like a platform outage for a day.

Six findings in total are reproduced from the repo and written up in `docs/UPSTREAM.md`.

## Accomplishments that I'm proud of

Both arms of the evaluation run, and both are scored:

| arm | accuracy | precision | recall | $ overbilled | $ missed | $ hour error |
|---|---|---|---|---|---|---|
| keyword triage | 12% | 0% | 0% | $170.00 | $425.00 | $0.00 |
| **gpt-6.1-sol** | **100%** | **100%** | **100%** | **$0.00** | **$0.00** | −$42.50 |

The last column is the one the model loses. It gets every call right and still estimates one
event at 1.5 hours against a label of 2.0 — **$42.50 the client is not charged**. The harness
reports it because a run that gets every decision right can still bill the wrong amount, and
scoring only the decisions would have hidden that.

The baseline bills a request for a copy of an old invoice, bills the *ask* rather than the work
that answered it, and misses both pieces of real out-of-scope engineering. The model gets all
eight right and cites a clause and a quoted span for every one.

**Eight events is a smoke test, not a benchmark**, and the repository says so in those words. So
there is a second result that is less flattering and more honest: 31 events from real pull-request
threads, labelled by six readers, four of whom were blind — they worked from a frozen written
instruction and had seen neither each other nor this repository. They agree at Krippendorff's
α = **0.797**. The model, asked the same question, manages **61.3%**. That number is in the
README beside the 100%.

## What I learned

That a found objection is a work item, not a verdict — and that the things worth writing down
are the ones that were quietly wrong. Two audits of my own code found an unauthenticated endpoint
that could release the double-billing guard, a dashboard that declared filter and sort pushdown
and honoured neither, and a money tool offered to the model with nothing wired to run it. Each is
fixed, each has a test, and each test was run against the old code to confirm it fails there.

## What's next for unlogged

A real past engagement — the real thread, the real commits, and the invoice that was actually
sent at the time. That invoice predates this product, so it is the one piece of ground truth that
cannot have been shaped by it, and it is what turns eight events into a result.

---

## The other fields on this page

**Built with** (tags, max 25)

```
python, fastapi, pydantic, uv, httpx, openai, openai-responses-api, paypal, paypal-invoicing-v2,
paypal-webhooks, paypal-sandbox, nextjs, react, typescript, ag-grid, ag-studio, tailwindcss,
docker, pytest, hypothesis, github-actions
```

**"Try it out" links**

| Label | URL |
|---|---|
| Source code | `https://github.com/aviralgarg05/unlogged` |
| The live invoice, $520 → $902.50 | `https://www.sandbox.paypal.com/invoice/payerView/details/INV2-DP6S-XFGQ-67JW-TMQL?qr=1` |

**Image gallery**, in this order:

1. `docs/img/payer-after.jpg` — the client's invoice at $902.50, both discovered lines named
2. `docs/img/payer-before.jpg` — the same invoice at $520.00
3. `docs/img/dashboard-decisions.jpg` — each event against the scope, with the clause and the span
4. `docs/img/dashboard-bill.jpg` — what reached the bill
5. `docs/img/dashboard-thread.jpg` — the raw work surface

**Video** — YouTube, public or unlisted with no password, under 3 minutes.
