# What is real, what is simulated, and what is not yet true

Written so a judge does not have to find any of this out by reading the source.

## Verified against PayPal's live sandbox

| Claim | Evidence |
|---|---|
| An already-sent invoice can grow line items while its id, payer URL and QR stay valid | `$520.00 → $902.50` on 2026-10-15, reproducible offline from `cassettes/`. Re-run it live with `uv run scripts/verify.py --live` |
| Each added line appears by name on PayPal's hosted payer page | `docs/img/payer-before.jpg` and `payer-after.jpg` — invoice #0036 at $520.00 and at $902.50, same id, same URL, shot minutes apart. Reproduce with `scripts/verify.py --live` |
| Every scope clause reaches the payer, labelled with the id its verdicts cite | `detail.terms_and_conditions` rendered under its own heading — `docs/img/payer-after.jpg`, directly below the two lines that cite `X1` |
| Money paid outside PayPal can be recorded, and a later line does not discard it | `POST /invoices/{id}/payments`: $100.00 BANK_TRANSFER moves a $690.00 invoice to PARTIALLY_PAID with $590.00 due; a further item leaves $675.00 due with the payment intact. Two checks in `scripts/verify.py --live` |
| A recipient-less invoice is legal | `invoice.required` is `["detail"]` only, confirmed against the published schema — and sent recipient-less live, 200 and `UNPAID`, on 2026-10-16 UTC |
| Silent send lands on `UNPAID` with no email | `POST /{id}/send` with both notify flags false. **Only for an invoice dated today or earlier in UTC.** A future `invoice_date` makes the send scheduled: 202 and `SCHEDULED` with a recipient, 422 `MISSING_RECIPIENT_EMAIL` without one. Three cases in [`VERIFIED.md`](VERIFIED.md), filed upstream |
| `early_payment_discount` is accepted with 201 and silently dropped | `scripts/repro_discount_defect.py`, four term/date combinations |
| `POST /conditional-rules` returns 500 | Same script. The schema's only non-`links` property is `readOnly` |

## Simulated, and labelled as such in the product

- **Webhook delivery.** The demo drives `INVOICING.INVOICE.PAID` through PayPal's sandbox
  simulator rather than waiting on a buyer. Simulator events cannot be postback-verified, so
  `/webhook` accepts them and returns `simulated: true` instead of treating them as genuine.
  Real deliveries are verified over the raw bytes against PayPal's own endpoint.
- **Replay.** `UNLOGGED_REPLAY=1` is the default. Responses come from `cassettes/`, which were
  recorded from real sandbox calls — not hand-written. Set `UNLOGGED_REPLAY=0` with credentials
  to go live.

## Not yet true

- **The model scores 100% on eight events, and eight events is not a benchmark.** It is a
  smoke test that the arm works end to end, and it should be read as nothing more. The honest
  reading: on a set this small, with two positives, a single different judgement would move
  precision by a third. What it does establish is that the arm runs, that every verdict cites
  a clause and quotes the span it relied on, and that it separates the request (`e1`) from the
  work that answered it (`e3`) — the distinction the baseline cannot make and the one that
  causes double-billing. A real engagement of 40-60 events is what would make this a result.
- **The grounding check narrows prompt injection; it does not stop it.** A verdict is
  refused if it cites a clause the engagement does not have or quotes words the event does
  not contain. That catches a model talked into inventing a citation, which is what a crude
  injection produces. It cannot catch an attacker who writes the sentence first: a pull
  request comment containing "the full payment-provider migration, 40 hours of engineering"
  is a verbatim span of a real event, so a verdict quoting it is grounded by construction.
  What bounds that case is arithmetic rather than text — hours cap at 40, the agreed cap is
  enforced against the document being written and inside the lock that writes it (it was
  enforced against an earlier read, which is not a bound), the rate card prices it, and every
  line is on the client's own page citing the clause it rests on, where a person can argue
  with it. Whether the model
  complies with such an instruction at all is untested here.

- **There is real data in this repository, and it says the model is worse than the headline.**
  31 events from real pull-request threads are committed under `fixtures/agreement/`, labelled
  by six readers and by the model. Four of those readers were blind: they worked from the
  frozen instruction in [`LABELLING.md`](LABELLING.md) and had seen neither each other, nor the
  earlier passes, nor any critique, nor this repository. They agree at Krippendorff's alpha
  **0.797**, call 25 of 31 events identically, and one of them matches the majority of the
  others **94.3%** of the time. The model, asked the same question, manages **61.3%**. Run `uv
  run unlogged agreement`. [`CORPUS.md`](CORPUS.md) is the full account, including the error
  that was mine.

- **What is still missing is a usable gold set, not data.** None of the fourteen engagements
  built in the first two rounds survived the independent reader whose job was to break it, so
  there is no adjudicated set to score an arm against — which is why the accuracy table in the
  README is still eight authored events, and why it now carries the real-data result beside it
  rather than below it.

- **Two of the six readers are not independent.** `round1` and `round2` are a pass and its own
  informed revision: the second was shown a critique of the first. Their 0.72 is reported for
  completeness and is not the headline. The 0.797 comes from the four who saw nothing, and the
  blindness is checkable rather than asserted — every tool call those four made is `gh api`
  against the source repository from a scratch directory.

- **All six readers are language models, not people.** The figure measures how reproducible the
  written instruction is under careful independent reading, which is the question that matters
  for whether the labels mean anything. It is not a claim about human annotators, and two model
  families were used rather than one so it is not a claim about a single model's habits
  either.

- **The events can be real; the agreement still is not.** `unlogged pull-github` pulls a
  genuine thread out of a repository, which removes the worst circularity — that one person
  wrote the events, the labels and the arm. It does not remove the other one: the scope
  clauses a verdict cites still have to come from somewhere, and a scope written after
  reading the work is a scope fitted to the answer. Any engagement in this repo whose clauses
  were written retrospectively is labelled here, in this file, by name.

- **The seeded ledger is fixture data.** `data/seed/eng-checkout-001.jsonl` holds two lines
  from an invented earlier billing period, so the page titled "Every line this system added to
  the live PayPal invoice" is not blank on a fresh clone. They are labelled with a
  `INV2-PRIOR-PERIOD-0001` invoice id that does not exist at PayPal. Everything dated
  2026-10-15 in that table is a real write to a real sandbox invoice.

- **The fixture engagement is authored, and that limits the 100% above more than its size does.**
  `fixtures/events.jsonl` and `fixtures/gold.jsonl` were written for this repo. They are a reasonable thread, but they are not evidence, and a labelled
  set written by the same person who writes the adjudicator is worth very little. The intended
  corpus is a real past engagement — the real thread, the real commits, and the invoice that was
  actually sent at the time — because that invoice predates this product and so cannot have been
  shaped by it. Until that exists, the eval measures the harness, not the claim.
- **Live mode is untested.** This PayPal account is registered in India, which is
  receive-and-withdraw only, so live-mode sending cannot be exercised. Sandbox accounts can be
  created in any country, which is what makes the cross-border case demonstrable at all.
- **The money tool could not run at all, and now can; a real model has still never called
  it.** `add_billable_work` was declared `kind: 'server'`, which in `ag-studio@3.0.0` builds a
  tool with a schema and `execute: undefined` — the library advertises it and leaves execution
  to the host, and there is no hook in the bundle that hands the call back. The host never
  executed it: `/api/ai/tool` exists for exactly this and nothing in the repository called it.
  So the headline AG Studio differentiator was a money tool offered to a model with nothing to
  run it. It is declared normally now and its `execute` is the round-trip to that route, with
  a refusal surfaced to the model rather than swallowed; five tests cover the dispatch and
  `web/lib/server-tools.ts` still covers the route. What is *still* untested is the last join:
  a real model emitting the call in a conversation. That needs an OpenAI key and has not been
  run.
- **Docker Compose is the verified path; Render is not.** `docker compose up` was run with an
  empty env file — exactly what a fresh clone has — and both halves came up: the API healthy
  and reporting `paypal_configured: false`, the web half reaching it over the compose network,
  the dashboard rendering the seeded ledger, and the documented apply flow replaying *inside*
  the API image to `USD 902.50`. Both images were opened afterwards: no `.env` anywhere in
  either, `data/seed/` present and nothing else under `data/`. Exactly one file in the web image
  matches `sk-[A-Za-z0-9]{20,}` — `@img/sharp-wasm32`'s wasm binary, whose matches are SVG
  attribute names with the leading `ma` eaten by the pattern: `sk-typefilterUnits`,
  `sk-modeyChannelSelector`, `sk-borderspecularExponent`. One file, several strings, no key.

- **The Render blueprint has never been deployed.** `render.yaml` is written and its two
  services are the ones this repo runs locally, but no deploy has been made from it, so what
  it claims is a configuration rather than a result. It did carry a real defect until it was
  read properly: a blueprint cannot put a scheme in front of a `fromService` value, so the web
  half was handed a bare `host:port` and could not reach its own API — and that failure reads
  as the API being down rather than as a bad address. `lib/backend-origin` fixes it and is
  tested against the exact strings Render produces, which is as far as testing can go without
  deploying.
- **Telemetry has been round-tripped but not scored.** `/api/telemetry` accepts and summarises
  batches, and the observer is registered on the harness. No AgentUnit evaluation consumes it
  yet, because there are no runs to consume.
- **The filter and sort pushdown is honoured, and was not.** The data source declared
  `capabilities: { pagination, filter, sort }` — which tells AG Studio not to filter or sort
  locally — while `getData` never read `options.sort` and flattened the filter into bare query
  parameters the endpoint did not declare, so FastAPI dropped them. Filtering the Adjudications
  grid returned every row with the filter chip showing. Both halves are implemented now and
  tested end to end, and an operator the service cannot apply is refused rather than ignored.
  What is worth stating: at eight rows the engine often holds the whole table and sorts it
  itself rather than asking again, so the pushdown is best seen against the API directly.

- **The evidence widget does not respect page filters.** It reads through `widgetApi.getData`
  when the saved report's field mapping resolves, and falls back to reading the backend directly
  when it does not. The card says which path it used rather than hiding it. The fallback exists
  because a card that silently shows nothing is worse than one that shows the right rows without
  a filter applied.
- **The widget declares no `formatShape`,** so the assistant can place and data-map it but not
  configure its format. That is not a choice — the public API makes a shape impossible to
  construct. Evidence and a suggested fix are in `docs/UPSTREAM.md`.
- **Hours are scored, and the model is worse at them than at the call.** This bullet said they
  were unmeasured, and that was true until `score()` learned to compare them: a run that got
  every call right could still bill the wrong amount, and the harness called it 100%. It now
  reports hours wrong and prices the gap at the rate card — `gpt-6.1-sol` estimates `e8` at 1.5
  hours against a label of 2.0, which is **$42.50 the client is not charged**, visible in the
  README's own table. What is still unmeasured is hour accuracy against anything but authored
  labels, for the same reason the call accuracy is: there is no adjudicated real gold set yet.

## Deliberately not built

- **No per-item approval modal.** The client is notified by PayPal on every change, which is
  PayPal's own `send_to_recipient` machinery. Adding a bespoke approval step would make this the
  same "AI proposes, human approves" shape as most of the field, and would not make the client
  any better informed than PayPal's own email already does.
- **No "un-retractable ceiling" claim.** An earlier design wrote a cap into the invoice and
  called it binding. It is not: `PUT` is a full-document replace, so the same call that changes
  the price can rewrite the cap. The cap is stated to the payer in `detail.note` as a commitment,
  and that is all it is.
