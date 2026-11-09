# Recording script

Everything needed to record, in order. Keep this open on a second screen.
Target **2:30**, hard ceiling 3:00. Direction and the reasoning behind each cut live in
[`VIDEO.md`](VIDEO.md) — this file is just what to open, what to run, and what to say.

---

## Before you roll

Three commands, three windows.

```bash
uv run scripts/rehearse.py                      # 1. proves the take works, opens this take's invoice
uv run uvicorn unlogged.web:app --port 8000     # 2. the service      (leave running)
cd web && npm start                             # 3. the dashboard    (leave running)
```

`rehearse.py` prints two things — **this take's payer URL** and **this take's apply command**.
Paste both into the boxes below. Re-run it for every take; each one gets a fresh invoice, so a
second take is never refused as already billed.

**This take** (filled by `rehearse.py`, replace each run):

| | |
|---|---|
| Payer URL | `https://www.sandbox.paypal.com/invoice/payerView/details/INV2-ZXEE-JB3P-Q3Q5-Z7FP?qr=1` |
| Invoice id | `INV2-ZXEE-JB3P-Q3Q5-Z7FP` |

### Window layout

- **Left** — terminal, font bumped up, and the dashboard at `http://localhost:3000/dashboard`
- **Right** — the payer URL above. **Open it once, before recording starts, and never touch the
  address bar again.** The whole point of the hero shot is that this page was never reopened.

### Every link you will show

| What | Where |
|---|---|
| The client's invoice (this take) | the payer URL above |
| Dashboard | `http://localhost:3000/dashboard` |
| Landing page | `http://localhost:3000/` |
| Repo (last frame) | `https://github.com/aviralgarg05/unlogged` |
| Sandbox buyer sign-in (final beat) | `https://www.sandbox.paypal.com/` |

---

## 0:00 – 0:12 · the problem

**Screen** — the Slack thread on the dashboard's first page, *The thread*. Scroll it slowly.

**Say** — nothing for four seconds. Let it scroll. Then:

> Three weeks of work. Somewhere in here is work nobody wrote down — and nobody got paid for.

Hold on this row for a beat:

> *"Can you also just add the retry logic when the card declines?"*

---

## 0:12 – 0:30 · the agreement, and the invoice

**Screen** — left: the scope clauses. Right: the payer page at **$520.00**.

**Say**

> This is what was agreed. Clause X1: *payment provider integration, retry and error-handling
> logic are not included.*
>
> And this is the invoice. The client has had this link since day one.

---

## 0:30 – 1:10 · the adjudication — this is the product

**Screen** — dashboard → **What was decided**. Each row: the call, the clause it relied on, the
exact span that decided it.

**Say** — three rows, and only what is on screen.

> *"Can you also just add the retry logic"* — that's a request. A request isn't work. The money
> attaches when it's done.

> *"PR #312: handle PSP timeout and 3DS re-challenge."* That's the work. It cites X1 — the clause
> that excludes it from the agreed scope. So it's billable.

> *"Could you also send me last month's invoice again? Lost it."* — noise. That's phrasing, not
> work.

---

## 1:10 – 1:35 · the ablation

**Run**

```bash
uv run unlogged evaluate --engagement fixtures/engagement.json \
  --events fixtures/events.jsonl --gold fixtures/gold.jsonl
```

**Screen** — two rows appear. Let them land before speaking.

**Say**

> Keyword triage — what people actually fall back on — gets zero precision and zero recall. It
> bills a hundred and seventy dollars it shouldn't, and misses four hundred and twenty-five
> dollars of real work.
>
> The model gets all three at a hundred percent.

Then, because a judge is already thinking it:

> Eight events is a smoke test, not a benchmark. The repo says so.

Both rows run with no API key.

---

## 1:35 – 2:05 · money moves — one unbroken take, no cut

**Run** — this take's command from `rehearse.py`:

```bash
UNLOGGED_DATA=".film/take" UNLOGGED_REPLAY=0 UNLOGGED_RECORD= \
  uv run unlogged discover --engagement fixtures/engagement.json \
  --events fixtures/events.jsonl --invoice-id INV2-ZXEE-JB3P-Q3Q5-Z7FP --apply
```

**Screen** — switch to the right window. **Refresh. Do not retype the URL.**
$520.00 becomes **$902.50**, two new lines, each naming where it came from.

**Say**

> Same invoice. Same link. Same QR. PayPal added those lines, and PayPal emailed the client that
> it changed.

Do not cut anywhere in this beat. A cut is where a judge assumes a trick.

---

## 2:05 – 2:20 · the client pays

**Screen** — sign in as the sandbox buyer at `https://www.sandbox.paypal.com/` and pay it. The
payer page does the proving: amount due goes to zero, PayPal marks it paid.

**Say** — nothing. Let PayPal's own page say it.

---

## 2:20 – 2:30 · what it is

**Say**

> Cross-border contractors bill through PayPal because that's the rail that reaches them. The
> work they never wrote down is the work they never got paid for. This writes it down.

**Last frame** — split screen:

```bash
uv run pytest -q
```

…green, beside `https://github.com/aviralgarg05/unlogged`.

---

## Rules while recording

- **No JSON on screen. Ever.** If it can only be shown as JSON, it belongs in the README.
- **Nothing claimed that isn't visible.** No line asserts anything the frame doesn't show.
- **Works with the sound off** — a number going up, new named lines, PayPal's page showing paid.
- **1080p.** Upload unlisted first, make it public before pasting the link into Devpost.

## After the recording

1. Make the repository public, then open it logged-out and check the README images load.
2. `uv run scripts/verify.py --live` on the day you submit — it prints that day's payer URL,
   which goes straight into the write-up.
3. Paste the link into Devpost and check it from the submission preview.
