# The three-minute video

Judged on Presentation, one of five equally weighted criteria, and the only artefact every judge
consumes end to end. Hard ceiling 3:00; target **2:30**, because a judge with hundreds of these
to get through rewards brevity and nothing here needs the extra thirty seconds.

Shot entirely on a laptop: two browser windows and a screen recorder. No location, no second
person, no physical shoot.

## The rule that governs every cut

**The client's PayPal page is the only thing that proves anything.** Our own grid is where the
reasoning is visible, but a judge has no reason to trust our grid. Every claim lands on PayPal's
hosted page, in PayPal's own typography, or it does not land.

## Shot list

**0:00–0:12 — the problem, in one sentence, over the thread.**
Scroll a real Slack thread. No voiceover for the first four seconds; just the scroll.
Then: *"Three weeks of work. Somewhere in here is work nobody wrote down, and nobody got paid
for it."* Hold on one message — *"can you also just add the retry logic"* — for a beat.

**0:12–0:30 — the agreement, and the invoice the client already has.**
Left window: the engagement's scope clauses, including `X1 — payment provider integration, retry
and error-handling logic are not included`. Right window: PayPal's payer page, `$520.00`,
bookmarked three weeks ago. *"This is the invoice. The client has had this link since day one."*

**0:30–1:10 — the adjudication. This is the product.**
The grid fills in, one row per event, each with its call, the clause it relied on, and the exact
span that decided it. Linger on three rows and say only what is on screen:
- the ask (`scope_request`) — *"a request is not work. The money attaches when it's done."*
- the PR that did it (`billable_extra`, cites `X1`)
- `could you also send me last month's invoice` → `noise` — *"that one is phrasing, not work."*

**1:10–1:35 — the ablation, on screen, not in the README.**
Run `uv run unlogged evaluate --engagement fixtures/engagement.json --events
fixtures/events.jsonl --gold fixtures/gold.jsonl`. Two rows appear: keyword triage at 0% precision and 0% recall,
$170 billed that should not have been and $425 of real work missed; then `gpt-6.1-sol` at 100%
on all three. Read the two columns that matter out loud and say nothing else — the table is the
argument. Add one sentence of honesty, because a judge will think it: *"Eight events is a smoke
test, not a benchmark. The repo says so."* Both rows run with no API key, which is why this beat
is reproducible rather than narrated.

**1:35–2:05 — money moves, on PayPal's page.**
One continuous take, no cut, because a cut is where a judge assumes a trick. Click apply. The
right window — **the same bookmarked page, never reopened, never reissued** — is refreshed. The
total is now `$902.50` and new lines have appeared, each naming where it came from:
`PSP timeout handling and 3DS re-challenge (github 03 Oct)`. *"Same invoice. Same link. Same QR. PayPal added
those lines, and PayPal emailed the client that it changed."*

**2:05–2:20 — the client pays.**
Pay it in the sandbox. The webhook lands, the row flips to PAID. Money arriving, on camera.

**2:20–2:30 — what it is.**
*"Cross-border contractors bill through PayPal because that's the rail that reaches them. The
work they never wrote down is the work they never got paid for. This writes it down."*
Last frame: the repo URL and `uv run pytest`, green.

## Rules for the edit

- **No JSON on screen.** Ever. If something can only be shown as JSON, it belongs in the README.
- **The hero shot is one unbroken take.** Rehearse it until it runs clean rather than cutting.
- **Works with the sound off.** A number going up, new named lines appearing, a row turning PAID.
- **Nothing is claimed that is not visible.** No voiceover asserts anything the frame does not show.
- **Record at 1080p**, upload unlisted first, make public before submitting.

## Shoot by

Rehearse from **1 November**. Record by **8 November** — two days of slack before the Nov 10
submission, which is itself two days before the Nov 12 deadline.
