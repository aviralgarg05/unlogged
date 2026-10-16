"""unlogged — open an engagement, discover work, watch the bill itemise itself."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import typer

from unlogged.config import Settings
from unlogged.ledger import Entry, Ledger, now
from unlogged.paypal import Invoices, LineItem, PayPalClient
from unlogged.paypal.client import PayPalError
from unlogged.paypal.invoices import MAX_ITEMS, TERMINAL_STATUSES, total_of
from unlogged.scope.baseline import KeywordBaseline
from unlogged.scope.models import Call, Engagement, WorkEvent, line_name, load_events

app = typer.Typer(add_completion=False, help=__doc__)

# Exhaustive by construction: a new Call member fails at import rather than at the first event
# that happens to use it. The previous dict was missing scope_request, and two of the eight
# recorded verdicts are scope_request, so the documented command died with a KeyError.
MARK: dict[Call, str] = {
    Call.BILLABLE_EXTRA: "+",
    Call.SCOPE_REQUEST: "?",
    Call.INCLUDED: "=",
    Call.NOISE: " ",
}
assert set(MARK) == set(Call), "every Call needs a mark"
# Overridable so a verification run gets a ledger of its own: the apply flow is now guarded
# by what has already been billed, so replaying it against a ledger that already contains the
# demo is correctly refused, and a check meant to exercise the flow would be testing the guard.
DATA = Path(os.environ.get("UNLOGGED_DATA", "data"))


def _engagement(path: Path) -> Engagement:
    return Engagement.model_validate_json(path.read_text())


def _adjudicator(eng: Engagement, settings: Settings, events: list[WorkEvent]):
    """The model when a key exists, the keyword baseline when it does not.

    The baseline is not a placeholder — it is the evaluation's ablation arm, and the
    project is expected to run and be judged on both.
    """
    from unlogged.scope.adjudicate import Adjudicator

    # Live with a key, or replayed from recorded verdicts without one. Every call site uses this
    # rule; gating on the key alone meant a reader with no account only ever saw the arm built
    # to lose — including in every screenshot taken of this product.
    if settings.model_ready or Adjudicator.recorded_for(eng, events):
        return Adjudicator(eng, settings.openai_api_key)
    typer.secho(f"Using the {settings.adjudicator_name()}.", fg=typer.colors.YELLOW)
    return KeywordBaseline(eng)


@app.command()
def open_engagement(
    engagement: Path = typer.Option(..., help="Engagement JSON"),
    invoice_date: str = typer.Option(..., help="YYYY-MM-DD"),
) -> None:
    """Issue the one invoice the client will keep for the whole engagement."""
    s = Settings.from_env()
    eng = _engagement(engagement)
    with PayPalClient(s) as c:
        inv = Invoices(c)
        opening = [
            LineItem(
                name=o.name,
                quantity=o.quantity,
                unit_price=o.unit_price,
                currency=eng.currency,
                unit_of_measure=o.unit_of_measure,
            )
            for o in eng.opening
        ]
        created = inv.create(
            items=opening,
            invoicer_name=eng.invoicer_name,
            recipient_email=eng.client_email,
            reference=eng.id,
            note=eng.payer_note(),
            terms=eng.payer_terms(),
            currency=eng.currency,
            invoice_date=invoice_date,
        )
        iid = created["id"]
        inv.send(iid, notify=False)
        typer.echo(json.dumps({"invoice_id": iid, "payer_url": inv.payer_url(iid)}, indent=2))


@app.command()
def discover(
    engagement: Path = typer.Option(...),
    events: Path = typer.Option(..., help="JSONL of WorkEvent"),
    invoice_id: str = typer.Option(...),
    apply: bool = typer.Option(False, "--apply", help="Write the billable extras to PayPal"),
) -> None:
    """Adjudicate work events, then itemise the billable extras onto the live invoice."""
    s = Settings.from_env()
    eng = _engagement(engagement)
    evs = load_events(events.read_text().splitlines())
    judge = _adjudicator(eng, s, evs)
    verdicts = judge.adjudicate(evs)
    by_id = {e.id: e for e in evs}

    billable = [v for v in verdicts if v.is_billable()]
    for v in verdicts:
        mark = MARK[v.call]
        typer.echo(f" {mark} [{v.call.value:14}] {by_id[v.event_id].text[:70]}")
        if v.quoted_span:
            typer.echo(f'      cites {v.clause_id}: "{v.quoted_span[:60]}"')

    if not apply:
        typer.echo(f"\n{len(billable)} billable extra(s). Re-run with --apply to write them.")
        raise typer.Exit()

    ledger = Ledger(DATA / f"{eng.id}.jsonl")
    with ledger.guard():
        _apply(s, eng, ledger, invoice_id, billable, by_id, judge)


def _apply(s, eng, ledger, invoice_id, billable, by_id, judge):
    """Everything from reading the ledger to recording the write, under one lock.

    Checking and then writing is check-then-act: two callers that read before either wrote
    both see nothing billed and the client is charged twice. The lock has to span the
    decision, not just the HTTP call.
    """
    uncitable = [v.event_id for v in billable if not v.is_citable()]
    if uncitable:
        # Not a judgement about which arm is better. A line the client cannot trace to a
        # sentence in their own agreement is the thing this product exists instead of, and it
        # must not reach their invoice whichever arm produced it.
        typer.secho(
            f"Refusing to bill {', '.join(uncitable)}: the verdict cites no clause, quotes "
            f"nothing, or describes no work. Nothing written.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    already = ledger.billed_to(invoice_id)
    repeats = sorted({v.event_id for v in billable} & already)
    if repeats:
        # The only guard that works. PayPal accepts PayPal-Request-Id on an invoice PUT and
        # ignores it: verified live on 2026-10-15, where the identical write sent twice took
        # a sandbox invoice from $225.00 to $250.00. The header is still sent, because it
        # costs nothing and may start working, but nothing may depend on it.
        typer.secho(
            f"Already billed to {invoice_id}: {', '.join(repeats)}. Nothing written.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    with PayPalClient(s) as c:
        inv = Invoices(c)

        current = inv.get(invoice_id)
        status = current.get("status", "")
        if status in TERMINAL_STATUSES:
            # The web path refused this and the CLI did not, so the documented command would
            # ask PayPal to grow a paid invoice and surface the refusal as a stack trace.
            typer.secho(
                f"{invoice_id} is {status} and cannot take items. Nothing written.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        items = []
        for v in billable:
            ev = by_id[v.event_id]
            rate = eng.rate_card.rate_for(v.category)
            items.append(
                LineItem(
                    name=line_name(v),
                    quantity=v.hours,
                    unit_price=rate,
                    currency=eng.currency,
                    provenance=ev.provenance,
                )
            )
        # Keyed on the events rather than the resulting document, so a retry produces the
        # same digest. That is necessary and not sufficient: PayPal ignores the header on a
        # PUT, so the ledger check above is what actually stops the second charge.
        key = hashlib.sha256(",".join(sorted(v.event_id for v in billable)).encode()).hexdigest()[
            :16
        ]
        # Checked HERE, before the intent rows, and not only inside add_items. Both of these
        # fire before a socket is opened, and raising after the intent rows left the work
        # blocked for good: the ledger is append-only and a ValueError is not a PayPalError,
        # so no void was written and no retry was ever allowed.
        on_invoice = current.get("detail", {}).get("currency_code")
        mismatched = sorted({i.currency for i in items if on_invoice and i.currency != on_invoice})
        if mismatched:
            typer.secho(
                f"{invoice_id} is in {on_invoice} and these lines are priced in "
                f"{', '.join(mismatched)}. Nothing written.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        if len(current.get("items", [])) + len(items) > MAX_ITEMS:
            typer.secho(
                f"{invoice_id} already carries {len(current.get('items', []))} lines; "
                f"PayPal accepts {MAX_ITEMS}. Nothing written.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        # The cap is printed on the client's own invoice, under "Agreed cap". Until now it
        # was decoration: nothing compared a total against it, so the one number the client
        # was asked to rely on was the one number never checked.
        if eng.cap is not None:
            projected = total_of(current) + sum((i.total for i in items), Decimal("0"))
            if projected > eng.cap:
                typer.secho(
                    f"{eng.currency} {projected:,.2f} would exceed the agreed cap of "
                    f"{eng.currency} {eng.cap:,.2f}. Nothing written.",
                    fg=typer.colors.RED,
                )
                typer.echo("Raise the cap with the client, or bill fewer of these.")
                raise typer.Exit(1)

        # Written before the money moves. The ledger is the only guard, and a guard recorded
        # after the write does not exist during the window it has to cover: a crash or a read
        # timeout between the PUT and the record leaves nothing behind, and the next run
        # bills the client again.
        for v, item in zip(billable, items, strict=True):
            ledger.append(
                Entry(
                    at=now(),
                    invoice_id=invoice_id,
                    event_id=v.event_id,
                    clause_id=v.clause_id,
                    line_name=item.display_name,
                    hours=v.hours,
                    unit_price=item.unit_price,
                    total_after=Decimal("0"),
                    adjudicator=judge.name,
                    confidence=v.confidence,
                    settled=False,
                )
            )

        try:
            updated = inv.add_items(invoice_id, items, notify=True, idempotency_key=key)
        except PayPalError as exc:
            if exc.never_dispatched:
                for v, item in zip(billable, items, strict=True):
                    ledger.append(
                        Entry(
                            at=now(),
                            invoice_id=invoice_id,
                            event_id=v.event_id,
                            clause_id=v.clause_id,
                            line_name=item.display_name,
                            hours=v.hours,
                            unit_price=item.unit_price,
                            total_after=Decimal("0"),
                            adjudicator=judge.name,
                            confidence=v.confidence,
                            settled=False,
                            voided=True,
                        )
                    )
            raise
        total = total_of(updated)
        for v, item in zip(billable, items, strict=True):
            ledger.append(
                Entry(
                    at=now(),
                    invoice_id=invoice_id,
                    event_id=v.event_id,
                    clause_id=v.clause_id,
                    line_name=item.display_name,
                    hours=v.hours,
                    unit_price=item.unit_price,
                    total_after=total,
                    adjudicator=judge.name,
                    confidence=v.confidence,
                )
            )
        typer.echo(f"\nTotal now {eng.currency} {total}")
        typer.echo(f"Client's page: {inv.payer_url(invoice_id)}")


@app.command()
def evaluate(
    engagement: Path = typer.Option(...),
    events: Path = typer.Option(...),
    gold: Path = typer.Option(..., help="JSONL of hand labels"),
    out: Path = typer.Option(Path("evals"), help="Where to write the report"),
) -> None:
    """Score every available arm against the hand labels and write the report."""
    from unlogged.eval.harness import Gold, report, score, write_junit

    s = Settings.from_env()
    eng = _engagement(engagement)
    evs = load_events(events.read_text().splitlines())
    labels = [
        Gold.model_validate_json(line) for line in gold.read_text().splitlines() if line.strip()
    ]

    arms = [KeywordBaseline(eng)]
    from unlogged.scope.adjudicate import Adjudicator

    # The model arm is scored whenever it can answer: live with a key, or replayed from
    # recorded verdicts without one. That is the point of recording them — a judge with no
    # OpenAI account still sees both arms, and nobody pays for the same calls twice.
    if s.model_ready or Adjudicator.recorded_for(eng, evs):
        arms.append(Adjudicator(eng, s.openai_api_key))
    else:
        typer.secho(
            "No OPENAI_API_KEY and no recorded verdicts — scoring the baseline arm only.",
            fg=typer.colors.YELLOW,
        )

    results = [score(a, evs, labels, eng) for a in arms]
    md = report(results, eng, labels)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(md)
    write_junit(results, out / "junit.xml")
    typer.echo(md)


@app.command()
def evaluate_corpus(
    corpus: Path = typer.Option(..., help="A directory of engagement folders"),
    out: Path = typer.Option(Path("evals/corpus"), help="Where to write the report"),
) -> None:
    """Score every arm across a corpus of separate engagements and write one report.

    Each subdirectory holds `engagement.json`, `events.jsonl` and `gold.jsonl`. Real work
    does not arrive as one agreement with one long thread; it arrives as a brief, a pull
    request answering it, and a short argument about whether what landed was what was asked
    for. Each of those is its own small engagement, and the corpus is the set of them.
    """
    from unlogged.eval.harness import Gold, combine, report, score, write_junit
    from unlogged.scope.adjudicate import Adjudicator

    s = Settings.from_env()
    engagements = sorted(d for d in corpus.iterdir() if (d / "engagement.json").exists())
    folders = [d for d in engagements if (d / "gold.jsonl").exists()]
    if not engagements:
        typer.secho(f"No engagements under {corpus}", fg=typer.colors.RED)
        raise typer.Exit(1)
    if not folders:
        # The NexumDB corpus is exactly this case and it is not a defect: no labelling of it
        # survived an independent reader, so there is no adjudicated gold to score against.
        # Crashing with a FileNotFoundError said none of that.
        typer.secho(
            f"{len(engagements)} engagement(s) under {corpus}, none with a gold.jsonl.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            "There is nothing to score an arm against. For the corpus in fixtures/nexumdb "
            "that is deliberate — see docs/CORPUS.md — and `uv run unlogged agreement` is "
            "the measurement that corpus supports."
        )
        raise typer.Exit(1)
    skipped = [d.name for d in engagements if d not in folders]
    if skipped:
        typer.secho(
            f"Skipping {len(skipped)} without gold.jsonl: {', '.join(skipped)}",
            fg=typer.colors.YELLOW,
        )

    per_arm: dict[str, list] = {}
    all_labels: list[Gold] = []
    for folder in folders:
        eng = _engagement(folder / "engagement.json")
        evs = [
            WorkEvent.model_validate_json(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
            if line.strip()
        ]
        labels = [
            Gold.model_validate_json(line)
            for line in (folder / "gold.jsonl").read_text().splitlines()
            if line.strip()
        ]
        all_labels += labels

        arms = [KeywordBaseline(eng)]
        if s.model_ready or Adjudicator.recorded_for(eng, evs):
            arms.append(Adjudicator(eng, s.openai_api_key))
        for arm in arms:
            per_arm.setdefault(arm.name, []).append(score(arm, evs, labels, eng))

    results = [combine(name, parts) for name, parts in per_arm.items()]
    first = _engagement(folders[0] / "engagement.json")
    md = report(results, first, all_labels)
    md = f"{md}\n\nScored across {len(folders)} engagements in `{corpus}`.\n"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(md)
    write_junit(results, out / "junit.xml")
    typer.echo(md)


@app.command()
def agreement(
    directory: Path = typer.Option(Path("fixtures/agreement"), help="A folder of label sets"),
) -> None:
    """Score every pair of label sets against each other.

    There is no gold standard here and the directory does not pretend otherwise: it holds one
    file per reader. Two are passes a human made over the same real pull-request threads, the
    second written after an independent reader attacked the first. One is the model's. With no
    ground truth the only honest question is how far each reader is from the others, and the
    useful comparison is how far the model sits from where two humans sit from each other.
    """
    import itertools

    from unlogged.eval.agreement import score as agreement_score

    def load(path: Path) -> dict[str, str]:
        out = {}
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                out[f"{row['issue']}:{row['event_id']}"] = row["call"]
        return out

    sets = {p.stem: load(p) for p in sorted(directory.glob("*.jsonl"))}
    if len(sets) < 2:
        typer.secho(f"Need at least two label sets in {directory}", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo("| pair | events | raw | Krippendorff alpha (95% CI) | Cohen kappa | Gwet AC1 |")
    typer.echo("|---|---|---|---|---|---|")
    for a, b in itertools.combinations(sets, 2):
        r = agreement_score(sets[a], sets[b])
        lo, hi = r.alpha_ci
        typer.echo(
            f"| {a} vs {b} | {r.n} | {r.raw:.1%} | {r.alpha:.3f} ({lo:.2f} to {hi:.2f}) "
            f"| {r.kappa:.3f} | {r.ac1:.3f} |"
        )

    spans = {len(r) for r in sets.values()}
    if len(spans) > 1:
        typer.echo(
            "\nRows cover different numbers of events — a set that labelled fewer of them is "
            "scored only on those. Compare two rows only when the `events` column matches."
        )

    # A panel is the thing a model should be measured against. Readers whose names begin
    # "blind-" saw the frozen guideline and nothing else: not each other, not the earlier
    # passes, not any critique. They are the only sets here whose agreement means what the
    # word usually means.
    from unlogged.eval.agreement import panel as panel_score

    blind = {k: v for k, v in sets.items() if k.startswith("blind-")}
    if len(blind) >= 3:
        result = panel_score(blind, model=sets.get("model"))
        typer.echo("\n" + result.table())
        typer.echo(
            "\nThe ceiling is leave-one-out: how often one reader matches the majority of the\n"
            "others. It is the same question asked of the model, which is the only fair one\n"
            "when there is no ground truth to be right about."
        )

    names = list(sets)
    first = sets[names[0]]
    typer.echo("\nWhere the readers split, by call:")
    for name in names:
        counts: dict[str, int] = {}
        for key in first:
            if key in sets[name]:
                counts[sets[name][key]] = counts.get(sets[name][key], 0) + 1
        rendered = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        typer.echo(f"  {name:<10} {rendered}")


@app.command()
def reconcile(
    engagement: Path = typer.Option(...),
    invoice_id: str = typer.Option(..., help="The invoice to check the ledger against"),
) -> None:
    """Check that every line the ledger says was billed is on the live invoice.

    Growing an invoice is read-modify-write and PayPal offers no way to make that safe: no
    ETag, no If-Match, and the idempotency header is ignored. Two processes writing to one
    invoice means one of them loses its items silently. This is how that gets found — by the
    contractor, deliberately, rather than by the client noticing the total is short.
    """
    s = Settings.from_env()
    eng = _engagement(engagement)
    ledger = Ledger(DATA / f"{eng.id}.jsonl")
    # One line per event, not one per row. Every write leaves two rows — an intent before the
    # money moves and a settled one after — so counting rows expected each line twice and
    # reported a correct invoice as half missing.
    # Under the lock, and by the same rule billed_to uses. Reading an in-flight apply from
    # outside the lock showed the intent rows without the settled ones and called a healthy
    # write a divergence; ignoring `voided` counted a released write twice over.
    with ledger.guard():
        latest: dict[str, Entry] = {}
        for e in ledger:
            if e.invoice_id == invoice_id:
                latest[e.event_id] = e
    live_rows = [e for e in latest.values() if not e.voided]
    discovered = [e.line_name for e in live_rows]
    unsettled = [e.line_name for e in live_rows if not e.settled]
    # The opening lines were put on the invoice when it was created and never passed through
    # the ledger, which records discovered work. Leaving them out made every clean invoice
    # report its own agreed scope as a line nobody could account for — the loudest possible
    # false alarm, on the one tool whose job is to be believed when it cries divergence.
    expected = [i.name for i in eng.opening] + discovered
    if not discovered:
        typer.echo(f"The ledger records nothing discovered against {invoice_id}.")
        raise typer.Exit()

    if unsettled:
        # The write was attempted and we never learned whether it landed. That is precisely
        # the case this command exists for, so it is said first rather than folded into the
        # comparison below.
        typer.secho(
            f"{len(unsettled)} line(s) were attempted and never confirmed:", fg=typer.colors.YELLOW
        )
        for name in unsettled:
            typer.echo(f"  {name}")
        typer.echo("")

    if s.replay:
        # A recording is a snapshot of the invoice as it stood when it was made, and the
        # ledger describes writes that snapshot never saw. Comparing them is not a
        # reconciliation — it reported the demo's own just-billed lines as missing, every
        # time, on the documented path. Saying so and stopping is the honest answer; printing
        # an alarm it cannot justify teaches a reader to ignore the one tool whose only value
        # is being believed.
        typer.secho(
            "Replaying, so there is nothing to reconcile against: the recorded invoice is a "
            "snapshot from when it was taped, not the invoice as it stands.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"The ledger records {len(discovered)} discovered line(s) against {invoice_id}. "
            "Set UNLOGGED_REPLAY=0 with sandbox credentials to compare them against PayPal."
        )
        raise typer.Exit()

    with PayPalClient(s) as c:
        missing, unexplained = Invoices(c).reconcile(invoice_id, expected)

    if not missing and not unexplained:
        typer.secho(
            f"{len(discovered)} discovered line(s) plus {len(eng.opening)} opening line(s), "
            f"and the invoice carries exactly those.",
            fg=typer.colors.GREEN,
        )
        raise typer.Exit()

    if missing:
        typer.secho(
            f"{len(missing)} billed line(s) are NOT on {invoice_id} — work the client has "
            f"not been charged for:",
            fg=typer.colors.YELLOW,
        )
        for name in missing:
            typer.echo(f"  {name}")
    if unexplained:
        typer.secho(
            f"\n{len(unexplained)} line(s) on {invoice_id} the ledger does not justify — the "
            f"client may be charged twice:",
            fg=typer.colors.RED,
        )
        for name in unexplained:
            typer.echo(f"  {name}")
    typer.echo("\nThe ledger and the invoice disagree.")
    raise typer.Exit(1)


@app.command()
def show(engagement: Path = typer.Option(...)) -> None:
    """Print the append-only change ledger for an engagement."""
    eng = _engagement(engagement)
    ledger = Ledger(DATA / f"{eng.id}.jsonl")
    with ledger.guard():
        summary = ledger.summary()
    typer.echo(json.dumps(summary, indent=2))


@app.command()
def pull_github(
    repo: str = typer.Option(..., help="owner/name"),
    out: Path = typer.Option(..., help="Where to write the events JSONL"),
    pr_detail: int = typer.Option(40, help="How many pull requests to fetch diff stats for"),
    include_bots: bool = typer.Option(False, help="Keep review bots and coverage reporters"),
) -> None:
    """Pull a real work thread from GitHub into the event format this project adjudicates.

    The evaluation shipped here runs on eight events written by the author of the arm being
    evaluated, which proves nothing. This is how that gets replaced with work that actually
    happened. Read-only; nothing is written to the repository.
    """
    from unlogged.sources import GitHub

    s = Settings.from_env()
    with GitHub(repo, token=s.github_token, replay=s.replay) as gh:
        events = gh.events(pr_detail=pr_detail, include_bots=include_bots)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(e.model_dump_json() + "\n" for e in events))

    authors = sorted({e.author for e in events})
    span = (
        f"{events[0].occurred_at:%d %b %Y} to {events[-1].occurred_at:%d %b %Y}" if events else "—"
    )
    typer.echo(
        json.dumps(
            {
                "repo": repo,
                "events": len(events),
                "authors": authors,
                "span": span,
                "written_to": str(out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
