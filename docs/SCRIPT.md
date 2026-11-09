# Recording script

Everything needed to record, in order. Keep this open on a second screen.
Runs about **2:58** as written, **2:42** without the payment beat; the ceiling is 3:00.
Direction and the reasoning behind each cut live in [`VIDEO.md`](VIDEO.md) — this file is
what to open, what to run, and what to say.

---

## Read this through once, out loud, before you record

The whole narration, as one piece. Say it the way you would explain it to another developer —
it is written to be spoken, not read. If a line makes you change your voice to say it, that is
the line to rewrite.

> Hi, I'm Aviral. I built this thing called unlogged.
>
> If you've done contract work you know this one. You agree a scope — then work turns up
> anyway — and the parts that weren't in it never reach the bill.
>
> This is three weeks of my own thread. Somewhere in here is work I never got paid for.
>
> This one. *"Can you also just add the retry logic when the card declines?"* That cost me an
> afternoon.
>
> And here's what we'd agreed. Clause X1 — retry and error handling, not included. So that
> afternoon was extra. I never wrote it down, and the invoice still says five hundred and twenty.
>
> So that's what this does. It reads the thread against the agreement.
>
> The ask is just a request — nothing's owed yet. Three days later, the work that did it:
> PR 312. Points at that same clause, which makes it billable. And this one only sounds like a
> request. Noise.
>
> Every row has to name its clause and quote the line that decided it.
>
> Okay — but how often is it right?
>
> The cheap way is keyword matching. Zero precision, zero recall — it bills a hundred and
> seventy it shouldn't and misses four twenty-five that was real. The model gets all three at a
> hundred. And eight events is a smoke test, not a benchmark — the repo says so.
>
> But deciding isn't billing. This is the part nobody does.
>
> Same page — I haven't touched the address bar. Five twenty, now nine-oh-two fifty. Two new
> lines, each saying where it came from. Same invoice, same link, same QR. PayPal emailed my
> client.
>
> So the client opens the link they've had since day one, and pays it.
>
> Two things make that work: PayPal's invoicing API, where a sent invoice can grow in place —
> that isn't documented, I found it and wrote it up — and a model that cites a clause before
> anything reaches the bill.
>
> Contractors like me bill through PayPal because it's the rail that reaches us. The work we
> never wrote down is the work we never got paid for. This writes it down.

359 words — about **2:28 spoken**, plus roughly thirty seconds of scroll, the apply
running, the refresh and the payment. Lands near **3:03**, inside the three-minute ceiling.
Those thirty seconds are the shots — don't talk over them. If it runs long, drop the payment.

---

## Before you roll

```bash
uv run scripts/rehearse.py
```

It proves the whole take works against a throwaway invoice, then opens a fresh one and prints
the two lines below with the id filled in. Run it again for every take — each gets its own
invoice, so a second take is never refused as already billed.

Then the two halves, in their own tabs. The service must be pointed at **this take's** invoice,
or the dashboard's button writes to the committed demo invoice, which is already at its final
total and answers 409:

```bash
UNLOGGED_DATA=".film/take" UNLOGGED_INVOICE_ID=INV2-DJNX-LHYE-QDV9-ASLR UNLOGGED_REPLAY=0 uv run uvicorn unlogged.web:app --port 8000
```

```bash
cd web && npm start
```

**This take** — the only thing you open by hand:

`https://www.sandbox.paypal.com/invoice/payerView/details/INV2-DJNX-LHYE-QDV9-ASLR?qr=1`

You never type an invoice id anywhere. `rehearse.py` writes it into `.film/take/`, the service
is told it on the command line above, and the dashboard asks the service.

**Left window** — `http://localhost:3000/dashboard`, and a terminal in the repo with the font
bumped up. **Right window** — the payer URL above. Open it once, before recording starts, and
never touch the address bar again.

### What you press, start to finish

| When | What you do |
|---|---|
| 0:00 | Sidebar → **The thread**, and scroll |
| 0:45 | Sidebar → **What was decided** |
| 1:22 | Type `./demo eval` — the only typing in the whole video |
| 1:45 | Tick the two **Billable extra** boxes → click **Add to the live invoice** |
| 1:55 | Switch right, **refresh** the payer page |
| 2:15 | Pay it as the sandbox buyer |
| 2:30 | Type `./demo tests` |

### Every link that appears on screen

| What | Where |
|---|---|
| The client's invoice (this take) | the payer URL above |
| Dashboard | `http://localhost:3000/dashboard` |
| Repo, last frame | `https://github.com/aviralgarg05/unlogged` |
| Sandbox buyer sign-in | `https://www.sandbox.paypal.com/` |

---

## The same thing again, with the screen and the keys

Same words. This column tells you where to be and what to press.

### 0:00 — who you are, and the thread

You on camera for the first line if you want, then dashboard → **The thread**. Scroll slowly.

> Hi, I'm Aviral. I built this thing called unlogged.
>
> If you've done contract work you know this one. You agree a scope — then work turns up
> anyway — and the parts that weren't in it never reach the bill.
>
> This is three weeks of my own thread. Somewhere in here is work I never got paid for.
>
> This one. *"Can you also just add the retry logic when the card declines?"* That cost me an
> afternoon.

### 0:28 — the agreement, and the invoice

Left: the scope clauses. Right: the payer page at **$520.00**.

> And here's what we'd agreed. Clause X1 — retry and error handling, not included. So that
> afternoon was extra. I never wrote it down, and the invoice still says five hundred and twenty.

### 0:45 — the adjudication

Dashboard → **What was decided**. Walk down three rows as you talk.

> So that's what this does. It reads the thread against the agreement.
>
> The ask is just a request — nothing's owed yet. Three days later, the work that did it:
> PR 312. Points at that same clause, which makes it billable. And this one only sounds like a
> request. Noise.
>
> Every row has to name its clause and quote the line that decided it.
>
> Okay — but how often is it right?

### 1:22 — the ablation

Let the two rows land before you say anything. Both run with no API key.

```bash
./demo eval
```

> The cheap way is keyword matching. Zero precision, zero recall — it bills a hundred and
> seventy it shouldn't and misses four twenty-five that was real. The model gets all three at a
> hundred. And eight events is a smoke test, not a benchmark — the repo says so.

### 1:45 — money moves · one unbroken take, no cut

On the evidence card, right: **tick the two `Billable extra` boxes**, then click **Add to the
live invoice**. The card answers in green — *Invoice now USD 902.50*, with both line names.
Then switch to the right window and **refresh — don't retype the URL**.

No cut anywhere in this beat: a cut is where a judge assumes a trick.

This is the product's own button, not a script, which is worth far more on camera than a
terminal. If you would rather not restart the service for a take, `./demo apply` does the same
thing and prints the real command before it runs.


> But deciding isn't billing. This is the part nobody does.
>
> Same page — I haven't touched the address bar. Five twenty, now nine-oh-two fifty. Two new
> lines, each saying where it came from. Same invoice, same link, same QR. PayPal emailed my
> client.

### 2:15 — the client pays

Sign in as the sandbox buyer at `https://www.sandbox.paypal.com/` and pay it. Then stop
talking — PayPal's page does the proving: amount due goes to zero.

*Running long? This is the beat to drop.*

> So the client opens the link they've had since day one, and pays it.

### 2:30 — what it's built on, and what it's for

Last frame, split: `./demo tests` green, beside `https://github.com/aviralgarg05/unlogged`.

> Two things make that work: PayPal's invoicing API, where a sent invoice can grow in place —
> that isn't documented, I found it and wrote it up — and a model that cites a clause before
> anything reaches the bill.
>
> Contractors like me bill through PayPal because it's the rail that reaches us. The work we
> never wrote down is the work we never got paid for. This writes it down.

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
