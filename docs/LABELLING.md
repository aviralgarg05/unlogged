# Labelling guideline, frozen 2026-10-16

The instruction given to every blind reader, unchanged between them, so that the agreement
between them measures the task rather than the brief. It is published because a reliability
figure quoted without the guideline that produced it is not reproducible.

It deliberately contains no examples drawn from the threads being labelled, no counts, and no
indication of how often any call should appear. Any of those would steer the readers toward
each other and inflate the agreement.

---

## What you are doing

A contracting engagement has a written agreement: a list of clauses stating what was to be
built. Work then happens on a thread — pull requests, issues, comments, reviews. Your job is to
place each event on that thread against the agreement, and to say which clause your decision
rests on.

## The four calls

**`included`** — the event is work that the agreement's task list asks for. The deliverable it
concerns appears in the clauses.

**`scope_request`** — someone asks for work that the agreement does not cover, and at the
moment of this event that work has **not been done yet**. The ask creates an obligation; it
does not create a charge.

**`billable_extra`** — work outside the agreement that **has been done**. The commit, diff or
file exists.

**`noise`** — not work and not a request for work. Thanks, status updates with no new
obligation, administrative chatter, a question that asks for nothing to be built.

## The distinction that matters most

A request and the work that answers it are **two separate events**. The obligation is created
when someone asks; the work exists when someone does it. Treating both as `billable_extra`
charges a client twice for one piece of work.

Decide which you are looking at by **time and evidence**, not by wording. Check whether the
work existed when the event was written. An event that announces completed work is a report of
the work, not the work itself — the work is the commit.

## When the agreement forbids nothing

Most agreements list what is in scope and stop there. Work can be outside the agreement simply
by being **absent from the task list**. When that is the case, cite the scope clause that
defines the list and say the work is absent from it. Do not invent a prohibition that is not
written down.

Some agreements also carry explicit exclusions. Where one exists and applies, cite it.

## Rules

1. **Cite a clause** for `included`, `billable_extra` and `scope_request`. `noise` cites
   nothing — a clause that says nothing about an event is not evidence about it.
2. **Quote verbatim.** Every quotation you give must be a character-for-character span of the
   clause or the event. Never paraphrase.
3. **One deliverable, one `billable_extra`.** If several events concern the same piece of work,
   only one of them can be the work; the others are the request, the status update or the
   acknowledgement.
4. **No hours, no money.** Nobody on these threads was paid and no rate was ever agreed.
5. **Reason from the text**, not from what a reasonable person would think. If your reason
   says what seems fair, the label is not sound.
6. **Label every event you are given.** If you genuinely cannot decide, say so in
   `uncertain` and still give your best call — an abstention is a gap in the data, and a
   reader who declines the hard events makes agreement look better than it is.
