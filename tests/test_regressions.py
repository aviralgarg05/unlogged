"""Locks on three defects that each made this project claim something untrue.

Grouped together because they share a shape: in all three the wrong behaviour looked exactly
like the right one, so nothing failed and the evidence agreed with the mistake.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from unlogged import cassette, dotenv
from unlogged.eval.harness import Gold, Result, money, score
from unlogged.paypal import client as ppclient
from unlogged.scope.models import Call, Engagement, Verdict, WorkEvent

HERE = Path(__file__).resolve().parents[1]


class FixedArm:
    name = "fixed"

    def __init__(self, verdicts: list[Verdict]):
        self._v = verdicts

    def adjudicate(self, events: list[WorkEvent]) -> list[Verdict]:
        return self._v


def _engagement() -> Engagement:
    return Engagement.model_validate_json((HERE / "fixtures" / "engagement.json").read_text())


# -- 1. right call, wrong hours ------------------------------------------------------------


def test_a_correct_call_with_the_wrong_hours_is_not_scored_as_perfect():
    """score() used to return as soon as the classes matched.

    An arm could bill the right work for the wrong number of hours and the report would print
    0 overbilled, 0 missed, $0.00 either way — while the invoice it wrote was short.
    """
    eng = _engagement()
    ev = WorkEvent(
        id="x1",
        source="github",
        author="dev",
        text="retry logic",
        occurred_at="2026-10-03",
    )
    got = Verdict(
        event_id="x1",
        call=Call.BILLABLE_EXTRA,
        hours=Decimal("1.5"),
        category="engineering",
        clause_id="X1",
        quoted_span="retry",
        work_description="Retry logic",
        reason="outside scope",
    )
    want = Gold(event_id="x1", call=Call.BILLABLE_EXTRA, hours=Decimal("2.0"))

    r = score(FixedArm([got]), [ev], [want], eng)

    assert r.correct == 1 and not r.overbilled and not r.missed
    # The call was right, so the classification columns stay clean — and the half hour it
    # did not bill shows up as its own number instead of disappearing.
    assert r.hours_wrong == ["x1"]
    assert r.money_hours == Decimal("-42.50")
    assert "-$42.50" in r.table_row()


def test_matching_hours_report_no_error():
    eng = _engagement()
    ev = WorkEvent(
        id="x1",
        source="github",
        author="dev",
        text="retry logic",
        occurred_at="2026-10-03",
    )
    got = Verdict(
        event_id="x1",
        call=Call.BILLABLE_EXTRA,
        hours=Decimal("2.0"),
        category="engineering",
        clause_id="X1",
        quoted_span="retry",
        work_description="Retry logic",
        reason="outside scope",
    )
    r = score(
        FixedArm([got]),
        [ev],
        [Gold(event_id="x1", call=Call.BILLABLE_EXTRA, hours=Decimal("2.0"))],
        eng,
    )
    assert not r.hours_wrong and r.money_hours == Decimal("0.00")


def test_money_puts_the_sign_outside_the_currency_symbol():
    assert money(Decimal("-42.50")) == "-$42.50"
    assert money(Decimal("0.00")) == "$0.00"


def test_the_report_table_header_matches_the_row_width():
    """A row with more cells than its header silently drops columns when rendered."""
    from unlogged.eval.harness import report

    out = report([Result(arm="a")], _engagement(), [Gold(event_id="e", call=Call.NOISE)])
    # The arm table is the first one; the report now also breaks the labels down by where
    # they came from, which is a second table and not what this is checking.
    header, rule, row = [line for line in out.splitlines() if line.startswith("|")][:3]
    assert header.count("|") == rule.count("|") == row.count("|")


def test_an_unpriced_corpus_reports_no_money_rather_than_zero_money():
    """Labels drawn from work nobody was paid for carry no hours. Printing $0.00 overbilled
    would read as a perfect score on a question that was never asked."""
    from unlogged.eval.harness import report

    out = report(
        [Result(arm="a", priced=False)],
        _engagement(),
        [Gold(event_id="e", call=Call.NOISE, provenance="ruling")],
    )
    row = next(line for line in out.splitlines() if line.startswith("| a |"))
    assert "$0.00" not in row
    assert row.count("—") == 4


def test_the_report_says_how_many_labels_its_own_author_wrote():
    from unlogged.eval.harness import report

    out = report(
        [Result(arm="a")],
        _engagement(),
        [
            Gold(event_id="e1", call=Call.NOISE, provenance="authored"),
            Gold(event_id="e2", call=Call.NOISE, provenance="ruling"),
        ],
    )
    assert "1 of 2 labels were written for this repository" in out
    assert "not knowing it would be used this way" in out


# -- 2. the .env file the README promises --------------------------------------------------


def test_dotenv_fills_only_variables_that_are_absent(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "export EXPORTED=yes\n"
        'QUOTED="in quotes"\n'
        "ALREADY=from-file\n"
        "FRESH=from-file\n"
        "PLACEHOLDER=\n"
        "not a pair\n"
    )
    monkeypatch.setenv("ALREADY", "from-environment")
    monkeypatch.delenv("FRESH", raising=False)
    monkeypatch.delenv("PLACEHOLDER", raising=False)

    filled = dotenv.load(env)

    assert os.environ["FRESH"] == "from-file"
    # The environment wins. Without this an explicitly blanked key would be handed straight
    # back, every keyless test would quietly run the live model, and the ablation arm would
    # be unreachable on the one machine that has credentials.
    assert os.environ["ALREADY"] == "from-environment"
    assert "ALREADY" not in filled
    assert os.environ["EXPORTED"] == "yes"
    assert os.environ["QUOTED"] == "in quotes"
    # `KEY=` in the shipped example file is a placeholder, not a value.
    assert "PLACEHOLDER" not in os.environ


def test_an_empty_string_in_the_environment_is_respected_as_empty(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-not-a-real-key\n")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    dotenv.load(env)

    assert os.environ["OPENAI_API_KEY"] == ""


def test_a_missing_dotenv_is_the_normal_case_and_not_an_error(tmp_path):
    assert dotenv.load(tmp_path / "nothing-here") == []


def test_settings_read_the_dotenv_file(tmp_path, monkeypatch):
    """The actual regression: the README said the service reads `.env` and nothing did."""
    from unlogged.config import Settings

    env = tmp_path / ".env"
    env.write_text("PAYPAL_CLIENT_ID=id-from-file\nPAYPAL_CLIENT_SECRET=secret-from-file\n")
    monkeypatch.setattr(dotenv, "ENV_FILE", env)
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)

    assert Settings.from_env().has_paypal is True


# -- 3. cassettes that have to represent a change in state ---------------------------------


def test_repeated_reads_of_one_key_replay_in_recorded_order(tmp_path, monkeypatch):
    """The invoice is read before the write and again after it, under one cassette key.

    Keyed by name alone the second recording overwrote the first, so replay could not
    reproduce the one thing the recordings exist to show: the total going up.
    """
    monkeypatch.setattr(ppclient, "CASSETTES", tmp_path)
    key = ppclient._cassette_key("GET", "/v2/invoicing/invoices/INV2-X", None)
    (tmp_path / f"{key}.json").write_text(json.dumps({"status": 200, "body": {"total": "520.00"}}))
    (tmp_path / f"{key}.1.json").write_text(
        json.dumps({"status": 200, "body": {"total": "902.50"}})
    )

    from unlogged.config import Settings

    s = Settings(client_id="", client_secret="", base_url="x", openai_api_key=None, replay=True)
    with ppclient.PayPalClient(s) as c:
        assert c.request("GET", "/v2/invoicing/invoices/INV2-X")["total"] == "520.00"
        assert c.request("GET", "/v2/invoicing/invoices/INV2-X")["total"] == "902.50"
        # Reads past the end hold at the final state rather than failing.
        assert c.request("GET", "/v2/invoicing/invoices/INV2-X")["total"] == "902.50"


def test_takes_are_ordered_numerically_not_lexically(tmp_path):
    """`.10` sorts before `.2` as text, which would replay a later state too early."""
    from unlogged import cassette

    for n in ["", ".2", ".10"]:
        (tmp_path / f"abc{n}.json").write_text("{}")
    assert [p.name for p in cassette.takes("abc", tmp_path)] == [
        "abc.json",
        "abc.2.json",
        "abc.10.json",
    ]


def test_re_recording_replaces_a_keys_whole_sequence(tmp_path):
    """Otherwise a shorter second run leaves a longer first run's tail behind it, and replay
    walks off the end of this run into the last one."""
    from unlogged import cassette

    tape = cassette.Tape(tmp_path)
    for i in range(3):
        tape.record("k", {"n": i})
    assert len(cassette.takes("k", tmp_path)) == 3

    again = cassette.Tape(tmp_path)
    again.record("k", {"n": 99})
    assert len(cassette.takes("k", tmp_path)) == 1
    assert cassette.Tape(tmp_path).replay("k") == {"n": 99}


def test_replaying_a_key_that_was_never_recorded_returns_nothing(tmp_path):
    from unlogged import cassette

    assert cassette.Tape(tmp_path).replay("never") is None


# -- 4. the clause a billed line cites has to reach the client ------------------------------


def test_payer_terms_carry_every_clause_with_the_ids_the_verdicts_cite():
    """The note holds one scope clause and the cap. The exclusions are what the billed lines
    cite, and they were not on the client's page at all — so the invoice charged for work
    justified by a sentence the payer had never been shown.
    """
    eng = _engagement()
    terms = eng.payer_terms()

    for clause in eng.clauses:
        assert f"[{clause.id}]" in terms, f"{clause.id} missing from the payer's page"
        assert clause.text in terms
    # X1 is the one both billed extras rest on.
    assert "Not included [X1]" in terms
    assert "Agreed cap: USD 1,200.00." in terms
    # PayPal truncates past 4000 characters, so the field must never be built longer.
    assert len(terms) <= 4000


def test_payer_terms_stay_within_paypals_field_limit():
    from unlogged.scope.models import ScopeClause

    eng = _engagement()
    eng.clauses = [ScopeClause(id=f"S{i}", kind="scope", text="x" * 500) for i in range(20)]
    assert len(eng.payer_terms()) == 4000


# -- 5. the committed recordings have to stay reachable ------------------------------------


def test_the_paypal_cassette_key_is_the_one_the_committed_recordings_were_written_under():
    """Moving the cassette code into a shared module changed `key(*parts)` to hash a tuple,
    which wrapped the payload in a list, changed every digest, and orphaned all 47 committed
    PayPal recordings at once. The whole suite stayed green, because no test replayed one.
    """
    from unlogged.paypal.client import _cassette_key

    # Pinned to the digest the recordings in cassettes/ were written under. If this changes,
    # the recordings are unreachable and the keyless path is gone, whatever the tests say.
    assert _cassette_key("GET", "/v2/invoicing/invoices/INV2-X", None) == (
        cassette.key({"m": "GET", "p": "/v2/invoicing/invoices/INV2-X", "b": None})
    )
    assert len(_cassette_key("GET", "/x", None)) == 20


def test_the_documented_command_replays_to_the_figure_the_readme_prints(tmp_path, monkeypatch):
    """The judge path, run the way the README writes it: no PayPal account, no OpenAI key,
    no GitHub token. If this stops printing 902.50 the images, the README and the invoice
    have stopped agreeing with the code."""
    from typer.testing import CliRunner

    from unlogged import cli

    monkeypatch.setattr(cli, "DATA", tmp_path)
    for var in ("OPENAI_API_KEY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("UNLOGGED_REPLAY", "1")

    invoice_id = (HERE / "fixtures" / "demo-invoice-id").read_text().strip()
    result = CliRunner().invoke(
        cli.app,
        [
            "discover",
            "--engagement",
            str(HERE / "fixtures" / "engagement.json"),
            "--events",
            str(HERE / "fixtures" / "events.jsonl"),
            "--invoice-id",
            invoice_id,
            "--apply",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "902.50" in result.output
    # And it is the model arm that got there, not the ablation.
    assert "Unspecified work" not in result.output


def test_the_recorded_opening_state_is_the_one_the_before_image_shows():
    from unlogged.config import Settings
    from unlogged.paypal import Invoices, PayPalClient
    from unlogged.paypal.invoices import total_of

    invoice_id = (HERE / "fixtures" / "demo-invoice-id").read_text().strip()
    s = Settings(client_id="", client_secret="", base_url="x", openai_api_key=None, replay=True)
    with PayPalClient(s) as c:
        opening = Invoices(c).get(invoice_id)

    assert total_of(opening) == Decimal("520.00")
    assert len(opening["items"]) == 1


def test_combining_engagements_recomputes_rates_from_totals_not_from_averages():
    """A corpus is many small agreements, not one long one. Averaging their percentages
    would weight a three-event thread the same as a thirty-event one."""
    from unlogged.eval.harness import combine

    small = Result(arm="a", n=3, correct=3, correct_billable=1)
    large = Result(arm="a", n=30, correct=15, correct_billable=5)
    large.overbilled = [f"e{i}" for i in range(5)]

    whole = combine("a", [small, large])

    assert whole.n == 33
    assert whole.correct == 18
    assert round(whole.accuracy, 4) == round(18 / 33, 4)
    # Not (100% + 50%) / 2.
    assert whole.accuracy != 0.75
    assert whole.precision == 6 / 11


def test_a_corpus_is_unpriced_only_when_every_part_is():
    from unlogged.eval.harness import combine

    assert (
        combine("a", [Result(arm="a", priced=False), Result(arm="a", priced=False)]).priced is False
    )
    assert (
        combine("a", [Result(arm="a", priced=False), Result(arm="a", priced=True)]).priced is True
    )


# -- 6. an agreement has versions, and the one in force is the one that governs -------------


def _clause(cid, text, kind="scope", when=None):
    from unlogged.scope.models import ScopeClause

    return ScopeClause(id=cid, kind=kind, text=text, in_force_from=when)


def test_a_clause_added_later_does_not_govern_earlier_work():
    """The mistake this encodes was made while building this project's own corpus: two rules
    were read from the current CONTRIBUTING.md and cited against pull requests from two
    months before those rules were written. Not fabricated text — fabricated authority.
    """
    from datetime import UTC, datetime

    eng = _engagement()
    eng.clauses = [
        _clause("S1", "Add a security audit step using cargo audit to CI"),
        _clause(
            "X9", "Avoid mixing unrelated fixes", "exclusion", datetime(2026, 2, 6, tzinfo=UTC)
        ),
    ]

    december = datetime(2025, 12, 8, tzinfo=UTC)
    assert [c.id for c in eng.clauses_at(december)] == ["S1"]

    february = datetime(2026, 2, 20, tzinfo=UTC)
    assert [c.id for c in eng.clauses_at(february)] == ["S1", "X9"]

    # An engagement whose clauses carry no dates is unaffected, which is why every recording
    # made before this existed still replays.
    assert len(_engagement().clauses_at(december)) == 5


def test_billing_against_a_clause_that_was_not_in_force_is_counted_separately():
    """The call can be right and the authority still absent, so this is not overbilling. The
    client is being charged under a term they had not agreed to when they asked for the work.
    """
    from datetime import UTC, datetime

    eng = _engagement()
    eng.clauses = [
        _clause("S1", "Add a security audit step"),
        _clause(
            "X9", "Avoid mixing unrelated fixes", "exclusion", datetime(2026, 2, 6, tzinfo=UTC)
        ),
    ]
    ev = WorkEvent(
        id="x1",
        source="github",
        author="dev",
        text="Also fixed the unrelated workflow",
        occurred_at="2025-12-08T19:50:58Z",
    )
    got = Verdict(
        event_id="x1",
        call=Call.BILLABLE_EXTRA,
        hours=Decimal("1"),
        category="engineering",
        clause_id="X9",
        quoted_span="unrelated",
        work_description="Workflow fix",
        reason="outside scope",
    )

    r = score(
        FixedArm([got]),
        [ev],
        [Gold(event_id="x1", call=Call.BILLABLE_EXTRA, hours=Decimal("1"))],
        eng,
    )

    assert r.anachronistic == ["x1"]
    # The classification was right, so it is not overbilling.
    assert not r.overbilled and r.correct == 1


def test_a_clause_in_force_is_not_flagged():
    from datetime import UTC, datetime

    eng = _engagement()
    eng.clauses = [_clause("X9", "No payment work", "exclusion", datetime(2025, 1, 1, tzinfo=UTC))]
    ev = WorkEvent(
        id="x1",
        source="github",
        author="dev",
        text="payment work",
        occurred_at="2026-10-03T00:00:00Z",
    )
    got = Verdict(
        event_id="x1",
        call=Call.BILLABLE_EXTRA,
        hours=Decimal("1"),
        category="engineering",
        clause_id="X9",
        quoted_span="payment",
        work_description="Payment work",
        reason="outside scope",
    )

    r = score(
        FixedArm([got]),
        [ev],
        [Gold(event_id="x1", call=Call.BILLABLE_EXTRA, hours=Decimal("1"))],
        eng,
    )

    assert r.anachronistic == []


def test_two_labels_for_one_event_is_an_error_not_a_silent_overwrite():
    """Building the lookup as a dict kept the last label and dropped the first, so a set with
    two opinions about an event scored as though it had one — against a label no reader of the
    file could tell was the one in use. A real corpus build produced exactly this.
    """
    import pytest

    eng = _engagement()
    ev = WorkEvent(
        id="x1", source="github", author="dev", text="work", occurred_at="2026-10-03T00:00:00Z"
    )
    got = Verdict(event_id="x1", call=Call.NOISE, reason="none")

    with pytest.raises(ValueError, match="more than one label for: x1"):
        score(
            FixedArm([got]),
            [ev],
            [
                Gold(event_id="x1", call=Call.INCLUDED),
                Gold(event_id="x1", call=Call.BILLABLE_EXTRA),
            ],
            eng,
        )


# -- 7. the guard that actually stops a second charge ---------------------------------------


def test_the_documented_apply_command_refuses_to_bill_the_same_work_twice(tmp_path, monkeypatch):
    """PayPal accepts PayPal-Request-Id on an invoice PUT and ignores it.

    Verified live on 2026-10-15: the identical write sent twice under one key took a sandbox
    invoice from $225.00 to $250.00. The CLI had no other guard and its own comment claimed
    the opposite — so running the documented command twice charged the client twice for one
    piece of work, which is the worst thing this product can do.
    """
    from typer.testing import CliRunner

    from unlogged import cli

    monkeypatch.setattr(cli, "DATA", tmp_path)
    for var in ("OPENAI_API_KEY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("UNLOGGED_REPLAY", "1")

    invoice_id = (HERE / "fixtures" / "demo-invoice-id").read_text().strip()
    argv = [
        "discover",
        "--engagement",
        str(HERE / "fixtures" / "engagement.json"),
        "--events",
        str(HERE / "fixtures" / "events.jsonl"),
        "--invoice-id",
        invoice_id,
        "--apply",
    ]

    first = CliRunner().invoke(cli.app, argv)
    assert first.exit_code == 0, first.output
    assert "902.50" in first.output

    second = CliRunner().invoke(cli.app, argv)
    assert second.exit_code == 1
    assert "Already billed" in second.output
    # And it names what it refused, rather than failing silently.
    assert "e3" in second.output and "e8" in second.output


def test_an_overlong_clause_list_is_refused_rather_than_clipped():
    """PayPal caps detail.terms_and_conditions at 4000 characters. Clipping silently takes the
    clause a billed line cites off the client's page, with no error anywhere — and an
    engagement with enough scope to overflow it is exactly the kind that gets disputed.
    """
    import pytest

    from unlogged.config import Settings
    from unlogged.paypal import Invoices, LineItem, PayPalClient

    s = Settings(client_id="", client_secret="", base_url="x", openai_api_key=None, replay=True)
    with PayPalClient(s) as c, pytest.raises(ValueError, match="4000"):
        Invoices(c).create(
            items=[LineItem("Scope", Decimal("1"), Decimal("1.00"))],
            invoicer_name="x",
            recipient_email=None,
            reference="r",
            note="n",
            terms="x" * 4001,
            invoice_date="2026-10-15",
        )


def test_the_hundred_and_first_line_is_refused_before_the_write():
    """PayPal accepts 100 items. Finding that out on the hundred-and-first discovered extra
    means the work is already done and the bill cannot carry it."""
    import pytest

    from unlogged.config import Settings
    from unlogged.paypal import Invoices, LineItem, PayPalClient
    from unlogged.paypal import invoices as inv_mod

    s = Settings(client_id="", client_secret="", base_url="x", openai_api_key=None, replay=True)
    with PayPalClient(s) as c:
        inv = Invoices(c)
        monkey = [{"name": f"line {i}"} for i in range(inv_mod.MAX_ITEMS)]
        inv.get = lambda _id: {"items": monkey, "detail": {"currency_code": "USD"}}
        with pytest.raises(ValueError, match="101 line items"):
            inv.add_items("INV2-X", [LineItem("one more", Decimal("1"), Decimal("1.00"))])
