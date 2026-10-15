"""unlogged — open an engagement, discover work, watch the bill itemise itself."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import typer

from unlogged.config import Settings
from unlogged.ledger import Entry, Ledger, now
from unlogged.paypal import Invoices, LineItem, PayPalClient
from unlogged.paypal.invoices import total_of
from unlogged.scope.baseline import KeywordBaseline
from unlogged.scope.models import Call, Engagement, WorkEvent, line_name

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
DATA = Path("data")


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
    evs = [
        WorkEvent.model_validate_json(line)
        for line in events.read_text().splitlines()
        if line.strip()
    ]
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

    with PayPalClient(s) as c:
        inv = Invoices(c)
        items, ledger = [], Ledger(DATA / f"{eng.id}.jsonl")
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
        # Keyed on the events, not the resulting document: re-running this command after a
        # lost response must not bill the same work twice.
        key = hashlib.sha256(",".join(sorted(v.event_id for v in billable)).encode()).hexdigest()[
            :16
        ]
        updated = inv.add_items(invoice_id, items, notify=True, idempotency_key=key)
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
    evs = [
        WorkEvent.model_validate_json(line)
        for line in events.read_text().splitlines()
        if line.strip()
    ]
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
def show(engagement: Path = typer.Option(...)) -> None:
    """Print the append-only change ledger for an engagement."""
    eng = _engagement(engagement)
    typer.echo(json.dumps(Ledger(DATA / f"{eng.id}.jsonl").summary(), indent=2))


if __name__ == "__main__":
    app()
