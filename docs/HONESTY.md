# What is real, what is simulated, and what is not yet true

Written so a judge does not have to find any of this out by reading the source.

## Verified against PayPal's live sandbox

| Claim | Evidence |
|---|---|
| An already-sent invoice can grow line items while its id, payer URL and QR stay valid | `$520.00 → $902.50` on 2026-10-15, reproducible offline from `cassettes/`. Re-run it live with `uv run scripts/verify.py --live` |
| Each added line appears by name on PayPal's hosted payer page | `docs/img/payer-before.jpg` and `payer-after.jpg` — invoice #0035 at $520.00 and at $902.50, same id, same URL, shot minutes apart. Reproduce with `scripts/verify.py --live` |
| Every scope clause reaches the payer, labelled with the id its verdicts cite | `detail.terms_and_conditions` rendered under its own heading — `docs/img/payer-after.jpg`, directly below the two lines that cite `X1` |
| Money paid outside PayPal can be recorded, and a later line does not discard it | `POST /invoices/{id}/payments`: $100.00 BANK_TRANSFER moves a $690.00 invoice to PARTIALLY_PAID with $590.00 due; a further item leaves $675.00 due with the payment intact. Two checks in `scripts/verify.py --live` |
| A recipient-less invoice is legal | `invoice.required` is `["detail"]` only, confirmed against the published schema |
| Silent send lands on `UNPAID` with no email | `POST /{id}/send` with both notify flags false |
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
- **The `kind: 'server'` tool has not been exercised end to end.** `add_billable_work` is
  declared to the model and its execution path (`web/lib/server-tools.ts`) is unit-tested in
  four cases — unknown tool refused, malformed arguments refused before anything reaches the
  money path, a well-formed call forwarded, a backend refusal surfaced rather than swallowed.
  What has *not* happened is a real model emitting that call and the result flowing back into a
  conversation, which has not been run. The declaration and the handler are both real; the
  join between them is untested.
- **Telemetry has been round-tripped but not scored.** `/api/telemetry` accepts and summarises
  batches, and the observer is registered on the harness. No AgentUnit evaluation consumes it
  yet, because there are no runs to consume.
- **The evidence widget does not respect page filters.** It reads through `widgetApi.getData`
  when the saved report's field mapping resolves, and falls back to reading the backend directly
  when it does not. The card says which path it used rather than hiding it. The fallback exists
  because a card that silently shows nothing is worse than one that shows the right rows without
  a filter applied.
- **The widget declares no `formatShape`,** so the assistant can place and data-map it but not
  configure its format. That is not a choice — the public API makes a shape impossible to
  construct. Evidence and a suggested fix are in `docs/UPSTREAM.md`.
- **Accuracy of hour estimates is unmeasured.** The adjudicator estimates hours for billable
  extras. Nothing yet checks those estimates against anything.

## Deliberately not built

- **No per-item approval modal.** The client is notified by PayPal on every change, which is
  PayPal's own `send_to_recipient` machinery. Adding a bespoke approval step would make this the
  same "AI proposes, human approves" shape as most of the field, and would not make the client
  any better informed than PayPal's own email already does.
- **No "un-retractable ceiling" claim.** An earlier design wrote a cap into the invoice and
  called it binding. It is not: `PUT` is a full-document replace, so the same call that changes
  the price can rewrite the cap. The cap is stated to the payer in `detail.note` as a commitment,
  and that is all it is.
