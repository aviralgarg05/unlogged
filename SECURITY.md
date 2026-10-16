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
relies on it. Reproduced live and filed upstream in [`docs/UPSTREAM.md`](docs/UPSTREAM.md).

The guard that does work is an **append-only ledger** under an `fcntl` file lock — a file lock
rather than a thread lock, because the CLI and the web service are separate processes against
one engagement. The read, the repeat check and the write happen inside one exclusive hold, so
two requests arriving together cannot both see an empty ledger and both pass. An intent row is
written *before* the PUT, because a guard recorded after the write does not exist during the
window it has to cover, and is voided if the call provably never reached PayPal.

The resource carries no ETag and the update accepts no `If-Match`, so two writers that each
read before either wrote lose one of the two lines with no error anywhere. Nothing can prevent
that from outside, which is why `unlogged reconcile` exists to find it after the fact.

Line items are only ever appended. Nothing in this project deletes a line, lowers a total, or
cancels an invoice — there is no `DELETE` and no call to the `cancel` link in the codebase.

## Reporting

Open an issue, or email the address on the committing account. This is a hackathon project and
carries no SLA.
