# Recording script

Everything needed to record, in order. Keep this open on a second screen.
Runs about **2:55**; the hard ceiling is 3:00. Direction and the reasoning behind each cut live in
[`VIDEO.md`](VIDEO.md) — this file is what to open, what to run, and what to say.

---

## Read this through once, out loud, before you record

This is the whole narration as one piece. It is one argument, told forwards — each part hands
off to the next, so if a line feels like it arrives from nowhere, that is the line to fix.

> Hi, I'm Aviral. This is unlogged — it finds work you did and never wrote down, and puts it on
> the invoice your client already has.
>
> Three weeks of work in a Slack thread. Somewhere in here is work I never billed for.
>
> That one. *"Can you also just add the retry logic when the card declines?"* That took an
> afternoon.
>
> And this is what we agreed. Clause X1 — retry and error-handling logic, not included. So that
> afternoon was extra. I never wrote it down, and the invoice still says five hundred and twenty.
> The client has had this link since day one.
>
> So — read the thread against the agreement.
>
> The ask is a request, not work — money attaches when it's done. Three days later, the work:
> PR 312, payment timeout and 3DS. It cites X1, which makes it billable. And this one only sounds
> like a request. Phrasing, not work.
>
> Every row names its clause and quotes the sentence that decided it. So how often is it right?
>
> The cheap way is keyword matching — zero precision, zero recall. It bills a hundred and seventy
> it shouldn't and misses four hundred and twenty-five that was real. The model gets all three at
> a hundred. Eight events is a smoke test, not a benchmark; the repo says so.
>
> But deciding isn't billing. This is the part nobody does.
>
> Same page — I haven't touched the address bar. Five twenty to nine hundred and two fifty. Two
> new lines, each naming where it came from. Same id, same link, same QR. PayPal added them, and
> emailed the client.
>
> So the client opens the link they filed on day one, and pays it.
>
> Two pieces: PayPal's Invoicing API, where a sent invoice grows in place — undocumented, and
> written up in the repo — and a model that must cite a clause before anything reaches the bill.
>
> Cross-border contractors bill through PayPal because that's the rail that reaches them. The
> work they never wrote down is the work they never got paid for. This writes it down.

348 words — about **2:24 spoken** at a calm pace, plus roughly thirty seconds of
scroll, the apply running, the refresh and the payment. That lands near **2:55**, inside the
three-minute ceiling but not by much. Those thirty seconds are the shots — do not talk over
them, and if you need to save time, the beat to lose is the payment.

---

## Before you roll

```bash
uv run scripts/rehearse.py                      # proves the take works, opens this take's invoice
uv run uvicorn unlogged.web:app --port 8000     # the service    (leave running)
cd web && npm start                             # the dashboard  (leave running)
```

`rehearse.py` prints **this take's payer URL** and **this take's apply command**. Both go in the
box below. Re-run it for every take — each gets a fresh invoice, so a second take is never
refused as already billed.

**This take:**

| | |
|---|---|
| Payer URL | `https://www.sandbox.paypal.com/invoice/payerView/details/INV2-D5CU-H9MQ-P9TH-LZYQ?qr=1` |
| Invoice id | `INV2-D5CU-H9MQ-P9TH-LZYQ` |

**Left window** — terminal, font bumped up, and `http://localhost:3000/dashboard`.
**Right window** — the payer URL above. Open it once, before recording starts, and never touch
the address bar again. The whole hero shot rests on that.

**Every link that appears on screen**

| What | Where |
|---|---|
| The client's invoice (this take) | the payer URL above |
| Dashboard | `http://localhost:3000/dashboard` |
| Landing page | `http://localhost:3000/` |
| Repo (last frame) | `https://github.com/aviralgarg05/unlogged` |
| Sandbox buyer sign-in | `https://www.sandbox.paypal.com/` |

---

## The same thing again, with the screen and the keys

Same words as above. This column tells you where to be and what to press.

### 0:00 — who, what, and the thread

Face or dashboard, your call, then dashboard → **The thread**. Scroll slowly.

> Hi, I'm Aviral. This is unlogged — it finds work you did and never wrote down, and puts it on
> the invoice your client already has.
>
> Three weeks of work in a Slack thread. Somewhere in here is work I never billed for.
>
> That one. *"Can you also just add the retry logic when the card declines?"* That took an
> afternoon.

### 0:22 — the agreement, and the invoice

Left: the scope clauses. Right: the payer page at **$520.00**.

> And this is what we agreed. Clause X1 — retry and error-handling logic, not included. So that
> afternoon was extra. I never wrote it down, and the invoice still says five hundred and twenty.
> The client has had this link since day one.

### 0:40 — the adjudication

Dashboard → **What was decided**. Walk down three rows as you say it.

> So — read the thread against the agreement.
>
> The ask is a request, not work — money attaches when it's done. Three days later, the work:
> PR 312, payment timeout and 3DS. It cites X1, which makes it billable. And this one only sounds
> like a request. Phrasing, not work.
>
> Every row names its clause and quotes the sentence that decided it. So how often is it right?

### 1:18 — the ablation

Let the two rows land before speaking. Both run with no API key.

```bash
uv run unlogged evaluate --engagement fixtures/engagement.json \
  --events fixtures/events.jsonl --gold fixtures/gold.jsonl
```

> The cheap way is keyword matching — zero precision, zero recall. It bills a hundred and seventy
> it shouldn't and misses four hundred and twenty-five that was real. The model gets all three at
> a hundred. Eight events is a smoke test, not a benchmark; the repo says so.

### 1:42 — money moves · one unbroken take, no cut

Say the first line, run it, then switch right and **refresh — do not retype the URL**.
No cut anywhere in this beat: a cut is where a judge assumes a trick.

```bash
UNLOGGED_DATA=".film/take" UNLOGGED_REPLAY=0 UNLOGGED_RECORD= \
  uv run unlogged discover --engagement fixtures/engagement.json \
  --events fixtures/events.jsonl --invoice-id INV2-D5CU-H9MQ-P9TH-LZYQ --apply
```

> But deciding isn't billing. This is the part nobody does.
>
> Same page — I haven't touched the address bar. Five twenty to nine hundred and two fifty. Two
> new lines, each naming where it came from. Same id, same link, same QR. PayPal added them, and
> emailed the client.

### 2:15 — the client pays

Sign in as the sandbox buyer at `https://www.sandbox.paypal.com/` and pay it. Then stop
talking — PayPal's page does the proving: amount due goes to zero.

> So the client opens the link they filed on day one, and pays it.

### 2:30 — what it is built on, and what it is for

Last frame, split: `uv run pytest -q` green, beside `https://github.com/aviralgarg05/unlogged`.

> Two pieces: PayPal's Invoicing API, where a sent invoice grows in place — undocumented, and
> written up in the repo — and a model that must cite a clause before anything reaches the bill.
>
> Cross-border contractors bill through PayPal because that's the rail that reaches them. The
> work they never wrote down is the work they never got paid for. This writes it down.

---

## While recording

- **No JSON on screen. Ever.**
- **Nothing claimed that isn't visible.** No line asserts anything the frame doesn't show.
- **Works with the sound off** — a number going up, new named lines, PayPal's page showing paid.
- **1080p.** Unlisted first; make it public before pasting the link into Devpost.

## After

1. Make the repository public, then open it logged-out and check the README images load.
2. `uv run scripts/verify.py --live` on the day you submit — it prints that day's payer URL,
   which goes straight into the write-up.
3. Paste the link into Devpost and check it from the submission preview.
