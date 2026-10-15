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

Every write to a live invoice carries a content-derived `PayPal-Request-Id`, so a retry after a
timeout cannot add the same line twice. The official agent toolkit sets this header on nothing.

Line items are only ever appended. Nothing in this project deletes a line, lowers a total, or
cancels an invoice.

## Reporting

Open an issue, or email the address on the committing account. This is a hackathon project and
carries no SLA.
