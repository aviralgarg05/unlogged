# The corpus that is not in this repository

The evaluation this project ships runs on eight events its author wrote. That is a smoke
test, and [`HONESTY.md`](HONESTY.md) has said so from the start. The obvious fix is to
replace the authored thread with a real one, so this was attempted properly, twice, against
a real repository. It did not produce a set worth shipping, and this is the account of why —
because the reason turns out to be the argument for the product.

## What was attempted

[`aviralgarg05/NexumDB`](https://github.com/aviralgarg05/NexumDB) is an open-source project
with 124 pull requests, and 359 events from 29 people once the review bots are dropped —
the figure the committed recording reproduces, which is 40 higher than the first count here
because the importer stopped after three pages and said nothing. It has the one property
that matters here: the
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

## Four blind readers

The first attempt at this measured the wrong thing. Two passes were compared, but the second
had been shown a critique of the first before it started — an informed revision, not a second
opinion — and the reliability literature is clear that such a design cannot produce a
reproducibility figure at all.

So it was done properly. The instruction was frozen into [`LABELLING.md`](LABELLING.md), which
contains no examples from these threads, no counts, and no hint of how often any call should
appear, because any of those would steer readers toward each other and inflate exactly the
number they are there to measure. Four readers then labelled all 31 events under that one
instruction, in parallel, having seen neither each other, nor the earlier passes, nor any
critique, nor this repository.

That last part is checkable rather than asserted: every tool call the four made is in the run
transcript, and all of it is `gh api` against the NexumDB repository from a scratch directory.
None of them opened a file in this project.

```bash
uv run unlogged agreement
```

| measure | value |
|---|---|
| readers | 4 |
| events at least two readers labelled | 31 |
| **Krippendorff's alpha across the panel** | **0.797** |
| events all four called the same way | 25 of 31 |
| **one reader against the majority of the others** | **94.3%** |
| **the model against that same majority** | **61.3%** |

### What that says

**The task is reproducible.** Four independent readers given one written instruction agree at
α = 0.80 and call four events in five identically. The earlier figure of 0.72, from the
contaminated pair, turns out to have *understated* what a clean protocol reaches.

**The ceiling is 94.3%, and it is measured rather than assumed.** Leave one reader out, take
the majority of the rest, and ask whether the held-out reader matches it. That is the same
question the model gets asked, and it is the only fair one when there is no ground truth to be
right about: not "is the model correct" but "does the model agree with a panel as well as a
member of that panel does".

**The model is 33 points below it.** 61.3% against 94.3%. Against each individual reader it
scores 58–61%, alpha 0.28 to 0.35 — the lower bounds of those intervals touch zero.

No verbal band is attached to any coefficient. The familiar "substantial / almost perfect"
labels were derived for two-category problems, are explicitly not recommended for a four-way
nominal judgement, and would be borrowing authority the number does not carry. Three
coefficients are reported — alpha as the primary, because the number of readers per item
varies across the corpus; Cohen's kappa because a reader will look for it; Gwet's AC1 because
about half of every thread is `noise` and that skew is what triggers the documented kappa
paradox — and all three were chosen before the numbers were seen.

### The six events the panel split on

| event | the four readers |
|---|---|
| #7 comment-3628789451 | included / scope_request / scope_request / scope_request |
| #7 comment-3628907319 | included / scope_request / scope_request / scope_request |
| #7 comment-3628920440 | noise / billable_extra / billable_extra / billable_extra |
| #7 comment-3628925741 | included / scope_request / noise / noise |
| #10 comment-3629161421 | noise / billable_extra / billable_extra / billable_extra |
| #11 comment-3635423731 | noise / noise / noise / billable_extra |

Four of the six are the same reader dissenting alone against a unanimous other three, always
in the same direction: calling `included` or `noise` where the others see work, or a request
for work, outside the task list. That reader labelled no `scope_request` and no
`billable_extra` on any of the 31 events. Of the remaining two, one is a different reader
dissenting alone and one is a genuine three-way split.

Which is the model's failure, in milder form, from a reader who could not see the model. It is
evidence that the request-versus-work boundary is genuinely the hard part of this task rather
than a quirk of one arm — and also that three readers in four get it anyway.

### The earlier passes, scored against the blind consensus

| pass | agrees with the blind majority | alpha |
|---|---|---|
| first pass | 80.6% | 0.685 |
| second pass (informed revision) | 74.2% | 0.596 |
| the model | 61.3% | 0.346 |

The contaminated passes were decent readings. The revision was not an improvement on the one
it revised, which is worth knowing about a protocol built on criticism.

### And then the model was given the same 31 events

```bash
uv run unlogged agreement
```

| pair | events | raw | Cohen's kappa | Gwet's AC1 |
|---|---|---|---|---|
| human first pass vs human second pass | 31 | 80.6% | 0.719 | 0.749 |
| model vs human first pass | 31 | 61.3% | 0.437 | 0.507 |
| model vs human second pass | 31 | 48.4% | 0.296 | 0.334 |

**On the eight authored events in `fixtures/` the model scores 100%. On 31 events from real
pull-request threads it agrees with a human reader less often than two human readers agree
with each other.** That is the finding, it cuts against this project's own headline number,
and it is reproducible from the committed label sets with no credentials.

The error is not noise. It is one direction:

| call | human first pass | human second pass | model |
|---|---|---|---|
| included | 7 | 5 | **18** |
| scope_request | 7 | 6 | 1 |
| billable_extra | 2 | 6 | 1 |
| noise | 15 | 14 | 11 |

The model calls more than half of everything `included`. On the ten events where both humans
agreed and the model did not, it answered `included` nine times. It is not guessing badly — it
is failing to find anything outside the agreement, which is the one job it has.

### The failure, isolated

The obvious suspect was the agreement itself. The fixture has two written exclusion clauses;
the December threads have none, because nothing in `CONTRIBUTING.md` at that date excluded
anything. So the same 21 December events were run twice, against the same two human readers,
with exactly one thing changed: a single synthetic clause added to the agreement, reading
*"Work not listed in the tasks above is not part of this issue."* Same events, same labels,
same model, one variable.

| the model is shown | vs human 1 | vs human 2 | calls `included` |
|---|---|---|---|
| the agreement as it stands | 52% | 33% | 13 of 21 |
| the agreement + a closure clause | 62% | 43% | 11 of 21 |
| *(the two humans, on these same 21)* | *76%* | | |

The closure clause helps, by about ten points in both directions, and it does not come close
to the human ceiling. The synthetic clause is in `fixtures/nexumdb-closure/` and is clearly
marked: it is an intervention to isolate a variable, and it is not in any repository anywhere.

But the interesting number is in a column the agreement statistic hides:

| call | human 1 | human 2 | model | model + closure |
|---|---|---|---|---|
| included | 4 | 2 | 13 | 11 |
| **scope_request** | **5** | **5** | **0** | **0** |
| billable_extra | 2 | 6 | 1 | 1 |
| noise | 10 | 8 | 7 | 9 |

**On these 21 events the model never once says `scope_request`.** Both humans say it five
times. Adding the clause does not recover a single one. Across all 31 events it returns
`scope_request` exactly once, on a thread whose agreement does carry exclusions — so the claim
is scoped to the 21, not stretched to the set.

On the authored fixture the model handles this distinction correctly — it marks the client
asking for retry-on-decline as a request and the PR that implemented it as the billable work,
which is the central worked example in this README. On a real thread it does not make the
distinction at all.

That distinction is the product. `Call.SCOPE_REQUEST` exists because a request and the work
answering it are two events, and billing both charges the client twice for one piece of work.
An arm that never emits it has collapsed the only safeguard against the most expensive error
in the domain — and it did so invisibly, because the fixture was written in a way that let it
succeed.

### Why this is not being fixed here

The obvious next move is to rewrite the prompt until `scope_request` reappears. That would be
tuning against the same 31 events the result is measured on, whose labels two readers already
disagree about on six of them. The number would improve and would mean nothing.

Fixing this honestly needs a held-out set that does not exist yet, which is the same problem
this document opened with. So it is written down as a known failure with its mechanism
identified, and the README says beside its own headline that the 100% is a fact about a
fixture.

### The disagreements are not scattered### The disagreements are not scattered

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
uv run unlogged pull-github --repo aviralgarg05/NexumDB --out /tmp/events.jsonl --pr-detail 60
```

Read-only, no token needed for a public repository, and the recorded thread replays from
`cassettes/` with nothing set at all. The rulings quoted above are in it.
