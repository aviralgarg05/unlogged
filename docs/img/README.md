# Images

Every one of these was captured from the running project, not mocked. The two payer pages are
PayPal's own hosted invoice page for a real sandbox invoice.

| file | what it is |
|---|---|
| `payer-before.jpg` | The client's PayPal invoice at $520.00, one line: the agreed scope |
| `payer-after.jpg` | The same invoice — same id, same URL, same QR — at $945.00, with two discovered lines each naming where the work came from |
| `landing.jpg` | The product's own front page |
| `dashboard-thread.jpg` | Every message, commit and call on the engagement, paged from the server |
| `dashboard-decisions.jpg` | Each event placed against the agreed scope, beside the evidence card. The baseline's two billings are drawn as defects because neither cites a clause |
| `dashboard-bill.jpg` | What reached the bill: the totals, the per-line chart, and the append-only ledger |

Reproduce the payer pages with `uv run scripts/verify.py --live`.
