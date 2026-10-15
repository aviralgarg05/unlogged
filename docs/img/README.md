# Images

Every one of these was captured from the running project, not mocked. The two payer pages are
PayPal's own hosted invoice page for a real sandbox invoice, invoice #0036, shot minutes apart.

| file | what it is |
|---|---|
| `payer-before.jpg` | The client's PayPal invoice at $520.00, one line: the agreed scope. The full clause list is under "Terms and conditions" |
| `payer-after.jpg` | The same invoice — same id, same URL, same QR — at $902.50, with two discovered lines each naming the work and the day it came from, above the exclusion `X1` that both of them cite |
| `dashboard-thread.jpg` | Every message, commit and call on the engagement, paged from the server |
| `dashboard-decisions.jpg` | Each event placed against the agreed scope, beside the evidence card: the call, the clause relied on, and the sentence quoted from the event |
| `dashboard-bill.jpg` | What reached the bill: the invoice total, what each discovered line added, and the append-only ledger across two billing periods |

Reproduce the payer pages with `uv run scripts/verify.py --live`.
