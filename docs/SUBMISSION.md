# Devpost submission — draft

## Before submitting — do these in order

The repository is **private** and stays private until the last of these. Devpost needs a
public link; a private one is a mechanical fail regardless of what is in it.

- [ ] `uv run scripts/verify.py` — 16 checks, all green, no credentials
- [ ] `uv run scripts/verify.py --live` — 24 checks, re-proves the mechanism against PayPal on
      the day of submission, and prints a payer URL that can go straight in the write-up
- [ ] Record the video. `docs/VIDEO.md` has the shot list. Presentation is one of five equally
      weighted criteria and is worth nothing unfilmed
- [ ] Re-read `docs/HONESTY.md` and make sure every ⏳ is still honest
- [ ] **Make the repository public**, then open the link in a logged-out window and confirm
      the README images load
- [ ] Paste the public link into Devpost and check it from the submission preview

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
`$520.00 → $902.50`, every added line rendered by name on PayPal's own hosted page, and
reproducible from committed cassettes without a PayPal account.

Three undocumented behaviours cost a day each and are written up in `docs/VERIFIED.md`:
`PUT` is a full-document replace and 400s on `calculation_error` if you echo back the
`amount.value` you just read; `generate-qr-code` returns `multipart/form-data`, not `image/png`;
and exactly three top-level invoice properties are readOnly, not the six commonly assumed.

## Six things filed upstream

Each one was found by building on the platform, each is reproducible from the repo, and each is
written up in `docs/UPSTREAM.md` rather than kept as a talking point:

1. **The documented discount path is accepted and not stored.** Created, sent, re-read fresh —
   four term/date combinations, absent every time, total never moving off the list price.
   `POST /conditional-rules` returns 500 for every payload shape its own spec suggests.
2. **`generate-qr-code` returns a base64 multipart envelope, not an image.** HTTP 200 and a
   plausible payload that is not a PNG. Reproducible in one curl.
3. **The APIMatic-generated Server SDK ships no Invoicing controller** — six controllers, none
   of them invoicing — which is why every invoice call here goes through httpx.
4. **A public AG Studio custom widget cannot declare `formatShape`.** The callback is handed
   `{ api, context }`, `ag-studio` exports no shape builder, and returning a plain object throws
   inside `hydrateWidget` and takes the dashboard down.
5. **`PayPal-Request-Id` is accepted on an invoice PUT and ignored.** The identical write sent
   twice under one key took a sandbox invoice from $225.00 to $250.00 — so a retry after a lost
   response bills the client again, and the header an integration trusts to prevent that does
   nothing. The resource carries no ETag and the update accepts no `If-Match` either, so two
   writers that read before either wrote lose one of the two lines with no error: $270.00 where
   $300.00 was billed. Both reproduced live and written up in `docs/UPSTREAM.md`.
6. **`send` blames a missing recipient when the invoice date is the problem.** A future
   `invoice_date` silently turns an immediate send into a scheduled one; without a recipient to
   schedule the email to, it is refused with `MISSING_RECIPIENT_EMAIL` on `field: invoiceId`.
   Add the recipient the error asks for and the 422 becomes a 202 and an invoice stuck in
   `SCHEDULED` that the client cannot pay. The variable is the date, and `date.today()` is wrong
   for a quarter of the day east of UTC.

## Challenges

PayPal's documented discount path does not work. `early_payment_discount` is accepted with
**HTTP 201 and then silently dropped** — tested across three payment-term types with the discount
date both today and in the future — and `POST /conditional-rules` returns **HTTP 500**, because
the only non-`links` property of its request schema is `readOnly`. The official agent toolkit's
`PROMPTS.md` documents only that path. An agent following the shipped guidance writes a discount,
is told it worked, and charges the customer full price.

Reproduction script and a suggested fix: `docs/UPSTREAM.md`.

## Accomplishments

The evaluation is the part worth pointing at, because both arms run and both are scored:

| arm | accuracy | precision | recall | $ overbilled | $ missed |
|---|---|---|---|---|---|
| keyword triage | 12% | 0% | 0% | $170.00 | $425.00 |
| **gpt-6.1-sol** | **100%** | **100%** | **100%** | **$0.00** | **$0.00** |

The baseline — what people actually fall back on — bills a request for a copy of an old invoice,
bills the ask rather than the work that answered it, and misses both pieces of real out-of-scope
engineering, including a PR whose own description says "not in the original scope". The model gets
all eight right and cites a clause and a quoted span for every one.

**Eight events is a smoke test, not a benchmark**, and `docs/HONESTY.md` says so along with what
would make it a result. The verdicts are recorded as cassettes, so a judge with no OpenAI account
reproduces the whole comparison in twenty seconds and it costs nobody anything.

## What I learned

That a found objection is a work item, not a verdict. The first version of this printed a price
ladder on a physical sticker. One afternoon of asking actual shopkeepers killed it: they forecast
quantity well, they settle in UPI, they price by weight and bargain verbally, and their QR already
lets the payer type any amount. The mechanism survived; the problem it was pointed at did not.

## What's next

A real past engagement — the real thread, the real commits, and the invoice that was actually
sent at the time. That invoice predates this product, so it is the one ground truth that cannot
have been shaped by it, and it is what turns eight events into a result.

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
