# Security

## Credentials

PayPal client id and secret are read from the environment by the Python service and are never
sent to the browser. The dashboard reaches PayPal only through `/api/backend`, and the one
mutating AI tool is declared client-side but executed server-side for this reason. There is no
`NEXT_PUBLIC_` PayPal variable anywhere.

`.env` is gitignored. No key is committed, including in cassettes — those record response bodies
only, never request headers.

## Webhooks

Verified over the **raw request bytes** against `/v1/notifications/verify-webhook-signature`.
Re-serialising the parsed JSON changes the payload and fails verification for reasons that look
like a signing bug. An unverified, non-simulated payload is rejected with 400.

Sandbox simulator events cannot be postback-verified. They are accepted and flagged
`simulated: true` rather than being silently treated as genuine.

## Money

Every write to a live invoice carries a content-derived `PayPal-Request-Id`, which the official
agent toolkit sets on nothing — **and which PayPal ignores on an invoice `PUT`.** This section
used to claim the header meant a retry could not add the same line twice. It does not: the
identical write, sent twice under one key, took a sandbox invoice from $225.00 to $250.00. The
header is still sent, because it costs nothing and may one day be honoured, but nothing here
relies on it. Reproduced live and written up in [`docs/UPSTREAM.md`](docs/UPSTREAM.md).

The guard that does work is an **append-only ledger** under an `fcntl` file lock — a file lock
rather than a thread lock, because the CLI and the web service are separate processes against
one engagement. The read, the repeat check and the write happen inside one exclusive hold, so
two requests arriving together cannot both see an empty ledger and both pass. One lock for the
directory, not one per engagement file: the guard deliberately reads every ledger there, because
the invoice does not know what the engagement is called, and a lock narrower than what it reads
is not a lock — two writers billing one invoice under two engagement names took different locks
and both got through. An intent row is
written *before* the PUT, because a guard recorded after the write does not exist during the
window it has to cover, and is voided if the call provably never reached PayPal.

The agreed cap is enforced against the document the write is about to replace, inside the same
per-invoice lock — not against a read the caller took before it decided to write. Between those
two reads an invoice can gain a line from the other half of a double-click, from the CLI running
beside the service, or from a hand edit in PayPal's own dashboard, and the number that passes the
ceiling is the one the client sees. A refusal raised there is a `Refused`, which says nothing was
sent, so the intent rows are released rather than leaving real work unbillable for good.

The resource carries no ETag and the update accepts no `If-Match`, so two writers that each
read before either wrote lose one of the two lines with no error anywhere. Nothing can prevent
that from outside, which is why `unlogged reconcile` exists to find it after the fact.

Because that ledger is the only guard, what can reach it matters as much as what it does.
`/api/telemetry` takes no credential — the observer posting to it runs in a browser — and it
used to append caller-supplied JSON into the ledger's own directory, which the guard read as
rows. An unauthenticated POST could release the guard, so the next apply re-billed work already
on the invoice, or jam it, so real work could never be billed again. Telemetry now writes
outside that directory and each line is nested under `event`, so it cannot parse as a row; the
ledger reads only files that are ledgers. Both directions are reproduced in
`tests/test_web.py`, and both fail against the old code.

Line items are only ever appended. Nothing in this project deletes a line, lowers a total, or
cancels an invoice — there is no `DELETE` and no call to the `cancel` link in the codebase.

## Reporting

Open an issue, or email the address on the committing account. This is a hackathon project and
carries no SLA.
