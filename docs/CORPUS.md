# The corpus that is not in this repository

The evaluation this project ships runs on eight events its author wrote. That is a smoke
test, and [`HONESTY.md`](HONESTY.md) has said so from the start. The obvious fix is to
replace the authored thread with a real one, so this was attempted properly, twice, against
a real repository. It did not produce a set worth shipping, and this is the account of why —
because the reason turns out to be the argument for the product.

## What was attempted

[`aviralgarg05/NexumDB`](https://github.com/aviralgarg05/NexumDB) is an open-source project
with 124 pull requests, and 319 events from 25 people once the review bots are
dropped. It has the one property that matters here: the
work was **briefed before it was done**. Each issue carries a task list and a YAML block;
`CONTRIBUTING.md` was committed on 2025-12-05T17:23:28Z and the first external pull request
arrived fifteen hours later, on 2025-12-06T08:37:34Z. The agreement predates the work, which
is the single thing an invented scope can never claim.

Better still, people ruled on scope **in the thread, at the time**, with no idea it would
ever be used as ground truth:

> **nacholiya**: "Would you prefer: - I investigate and fix the Rust build issues in this PR,
> or - Keep this PR scoped to the CI guard and handle Rust fixes separately?"
>
> **aviralgarg05**: "Thanks for checking. Please keep this PR scoped to the CI guard change
> only. The Rust build failures should be handled in a separate PR/issue."

> **ignorant05**: "…commit, which isn't related to the respective issue but i did it anyway…"

> **aviralgarg05**, on a pull request whose whole brief was *"Add a security audit step using
> `cargo audit` to CI"*: "Also fix the failing workflow", then "Still issues, fix it
> completely".

Every quote above was checked character-for-character against the GitHub API before it was
written down here.

## What happened

Nine issue-and-pull-request threads were turned into engagements, each with clauses quoted
verbatim from its brief and a label for every human event. Each one was then handed to a
second reader whose only instruction was to knock it down.

| round | threads | sound | anachronisms | invented clauses | unsupported labels | missing events | double-counted |
|---|---|---|---|---|---|---|---|
| 1 | 9 | **0** | — | 2 | 36 | — | — |
| 2 | 5 | **0** | 7 | 5 | 26 | 8 | 8 |

Round 2 was a repair: fewer threads, each one handed the critique of its first attempt and
told to answer it point by point. It found *more* defects, not fewer, because the second
round of critics was told what to look for.

## The defect that mattered

The first round was given two exclusion clauses to work with, taken from `CONTRIBUTING.md`:

> "Keep changes small and focused" · "Avoid mixing unrelated fixes"

Both are verbatim. Both were added on **2026-02-06T18:04:12Z**, two months after the pull
requests they were being cited against. A critic put it exactly right:

> *Not fabricated text, but fabricated authority.*

That error was mine, not the labellers'. I read the current file instead of the one in force,
and it is the same error the product exists to prevent, pointed the other way: a bill
justified by a term the client had not agreed to when they asked for the work. It is now
impossible to make here — a clause carries `in_force_from`, the adjudicator is shown the
agreement as it stood on the day of the event, and a verdict citing a clause not yet in force
is counted on its own line of the report.

Two more product defects came out of the same pass:

* **Review submissions were never collected.** `/pulls/{n}/comments` returns comments on
  lines of code; it does not return the reviews. Every "CHANGES_REQUESTED: Solve the issues"
  — a client saying this is not what was asked for — was missing from an importer built to
  find exactly those. 26 of them, all human.
* **Two labels for one event scored as one.** The lookup was a dict, so the second label
  silently replaced the first and the arm was measured against a label no reader of the file
  could identify. It now raises.

## How much the two passes actually agreed

"Fourteen attempts failed" is a story, not a measurement. It cannot tell a reader whether the
task is hard, whether the labellers were careless, or whether the disagreements were one
judgement repeating. So the two passes were scored against each other on the five threads both
of them labelled:

```bash
uv run unlogged agreement
```

| measure | value |
|---|---|
| events labelled by both passes | 31 |
| raw agreement | 80.6% |
| Cohen's kappa | 0.719 |
| Gwet's AC1 | 0.749 |

Both statistics are given because kappa has a known failure — the *kappa paradox* — where a
dominant category inflates the chance-correction term and collapses the score although the
raters agree on nearly everything. These categories are skewed, about half of every thread
being `noise`, so kappa alone would understate agreement in exactly the way that failure
predicts. AC1 is the standard answer to it. The marginals are printed beside them so the skew
is visible rather than asserted, and the implementation is checked against the textbook 2×2
example in `tests/test_agreement.py` — a statistic a project computes about itself is worth
nothing unless the arithmetic is right.

**κ = 0.72 is substantial agreement by the usual convention.** That is the honest headline, and
it is a different claim from "every engagement had a defect". Both are true: two readers agree
on four events in five, and an error anywhere still invalidates an engagement's totals.

One caveat that cuts the other way: the second pass was shown a critique of the first. That
pushes in both directions — shared framing raises agreement, and targeted corrections lower it
on exactly the events the critic named — so this figure is not clean inter-annotator agreement
between independent readers. It is agreement between a pass and its own informed revision.

### The disagreements are not scattered

| thread | event | first pass | second pass |
|---|---|---|---|
| #11 | comment-3632851856 | noise | billable_extra |
| #11 | comment-3635423731 | noise | billable_extra |
| #11 | comment-3640234629 | noise | billable_extra |
| #7 | pr-34 | included | billable_extra |
| #10 | comment-3633596094 | included | noise |
| #166 | comment-3956952147 | scope_request | noise |

Three of the six are one judgement on one thread: whether a contributor's status comment
reporting completed out-of-scope work is the work itself or merely talk about it. Two more are
the same boundary seen from the other side. That is the request-versus-work distinction, which
is the single thing this product is built around — `Call.SCOPE_REQUEST` exists precisely
because billing the ask and the work double-charges the client.

The disagreement is concentrated on the hardest and most expensive judgement in the domain.
That is not a labelling accident.

## Why there is still no corpus here

Agreeing on 80% of events is not the same as producing a set worth scoring an arm against. An
engagement's totals are wrong if *any* of its labels are, and after two rounds every
engagement still contained at least one defect an independent reader could name. The defects
were not sloppiness. They were the same four judgements, over and over:

1. **Was it asked for, or was it done?** A request and the work answering it are two events,
   and the commit log is the only way to tell which you are looking at. Labellers got this
   backwards in both directions, repeatedly.
2. **One deliverable, how many events?** A request, a status update, an acknowledgement and
   the commit can all point at one piece of work. Only one of them is the work.
3. **What carries the exclusion?** When nothing in the agreement forbids something, the thing
   is outside scope by *absence from the task list* — and a clause that says nothing about the
   event is not evidence for a call about it, however verbatim it is.
4. **Which version of the agreement?** See above.

A set that gets those wrong is worse than no set, because it would produce an accuracy number
that looks like evidence. So this project still reports its accuracy against eight authored
events, and says so in the table itself.

## What this is evidence of

Every one of these threads was read twice: once by someone building the labels and once by
someone whose only job was to break them. Both had the entire thread, the commit log, the diff
and the brief in front of them, and no time pressure. They agreed on four events in five —
and still, fourteen times out of fourteen, the second reader found something the first had got
wrong, concentrated on whether a sentence described work that had been done or work that had
merely been asked for.

The freelancer this product is for does that reconstruction from memory, three weeks later,
at midnight, against a client who remembers it differently. That is the problem. The
difficulty found here is not an obstacle to the argument; it *is* the argument.

## Reproducing any of it

```bash
uv run unlogged pull-github --repo aviralgarg05/NexumDB --out /tmp/events.jsonl
```

Read-only, no token needed for a public repository, and the recorded thread replays from
`cassettes/` with nothing set at all. The rulings quoted above are in it.
