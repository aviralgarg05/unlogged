# What is real, what is simulated, and what is not yet true

Written so a judge does not have to find any of this out by reading the source.

## Verified against PayPal's live sandbox

| Claim | Evidence |
|---|---|
| An already-sent invoice can grow line items while its id, payer URL and QR stay valid | `docs/VERIFIED.md`, raw bodies in `docs/DAY1.md`. `$520.00 → $690.00 → $817.50` on 2026-10-15 |
| Each added line appears by name on PayPal's hosted payer page | Screenshot of the rendered page, same document |
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

- **Model adjudication is not yet measured.** `scope/adjudicate.py` is written against the
  Responses API but has not been run: there is no API key on this project yet. Every number
  published so far is the keyword baseline's, and the baseline exists to lose.
- **The fixture engagement is authored.** `fixtures/events.jsonl` and `fixtures/gold.jsonl` were
  written for this repo. They are a reasonable thread, but they are not evidence, and a labelled
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
  conversation, because that needs an API key this project does not have yet. The declaration
  and the handler are both real; the join between them is untested.
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
