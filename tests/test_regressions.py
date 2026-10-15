"""Locks on three defects that each made this project claim something untrue.

Grouped together because they share a shape: in all three the wrong behaviour looked exactly
like the right one, so nothing failed and the evidence agreed with the mistake.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from unlogged import dotenv
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
    header, rule, row = (line for line in out.splitlines() if line.startswith("|"))
    assert header.count("|") == rule.count("|") == row.count("|")


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


def test_takes_are_ordered_numerically_not_lexically(tmp_path, monkeypatch):
    """`.10` sorts before `.2` as text, which would replay a later state too early."""
    monkeypatch.setattr(ppclient, "CASSETTES", tmp_path)
    key = "abc"
    for n in ["", ".2", ".10"]:
        (tmp_path / f"{key}{n}.json").write_text("{}")
    assert [p.name for p in ppclient._takes(key)] == ["abc.json", "abc.2.json", "abc.10.json"]


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
