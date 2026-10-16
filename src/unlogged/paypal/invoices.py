"""Invoicing v2, wrapped around the one mechanism this project is built on.

An invoice that has already been sent can grow line items. The invoice id, and
therefore the payer-view URL and the QR the client filed, stay valid, and PayPal
renders every new line on its own hosted page. Verified live on 2026-10-15:
$520.00 -> $902.50, id stable, each discovered item
named on the payer page. See docs/VERIFIED.md.

Deliberately NOT used: `detail.payment_term.conditional_rules.early_payment_discount`,
which PayPal accepts with HTTP 201 and then silently drops (tested with DUE_ON_RECEIPT,
NET_30 and DUE_ON_DATE_SPECIFIED, and with discount dates both today and future), and
`POST /conditional-rules`, which returns HTTP 500 because the only non-`links` property
of its request schema is readOnly. The official agent toolkit's PROMPTS.md documents
only that dead path.
"""

from __future__ import annotations

import base64
import hashlib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from typing import Any

from unlogged.paypal.client import PayPalClient

# Verified against the published 557,403-byte schema: exactly three top-level invoice
# properties carry readOnly. `status`, `due_amount` and `gratuity` do NOT,
# contrary to folklore.
READONLY = ("id", "parent_id", "links")
# PayPal's own documented bounds. Both are load-bearing for an invoice that grows over the
# life of an engagement, and both fail in ways the caller would otherwise discover late: the
# clause list disappears off the end of the payer's page, or the hundred-and-first discovered
# line is rejected after the work is already done.
TERMS_LIMIT = 4000
MAX_ITEMS = 100

# Growing an invoice is read-modify-write on a shared mutable document, and PayPal offers no
# primitive to make that safe: no ETag on the resource, no If-Match on the update, and the
# idempotency header is ignored. Verified live on 2026-10-16 — two adjudications that read the
# same invoice and then wrote produced a total of $270.00 with one of the two billed lines
# missing entirely. The loser is not told; the ledger says the work was billed and the invoice
# does not carry it.
#
# These locks close the window for writers in one process, which is the case this product
# actually creates: a web request and a CLI run, or two events adjudicated together. Writers in
# separate processes cannot be serialised from here at all, which is what `reconcile` is for.
_LOCKS: dict[str, Lock] = {}
_LOCKS_GUARD = Lock()


def _lock_for(invoice_id: str) -> Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(invoice_id, Lock())


# Writable per the schema, but server-computed; echoing them back on a PUT invites a 422.
COMPUTED = (
    "status",
    "payments",
    "refunds",
    "due_amount",
    "effective_due_amount",
    "effective_invoice_total",
)


@dataclass(frozen=True)
class LineItem:
    """One billable line.

    `provenance` rides in the name so the payer can see where the work came from.
    """

    name: str
    quantity: Decimal
    unit_price: Decimal
    currency: str = "USD"
    unit_of_measure: str = "HOURS"
    provenance: str | None = None

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.provenance})" if self.provenance else self.name

    @property
    def total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    def to_paypal(self) -> dict[str, Any]:
        return {
            "name": self.display_name[:200],
            "quantity": str(self.quantity),
            "unit_amount": {"currency_code": self.currency, "value": f"{self.unit_price:.2f}"},
            "unit_of_measure": self.unit_of_measure,
        }


class Invoices:
    def __init__(self, client: PayPalClient):
        self.c = client

    # -- lifecycle ----------------------------------------------------------

    def create(
        self,
        *,
        items: Iterable[LineItem],
        invoicer_name: str,
        recipient_email: str | None,
        reference: str,
        note: str,
        terms: str | None = None,
        currency: str = "USD",
        invoice_date: str,
        term_type: str = "NET_15",
    ) -> dict[str, Any]:
        """Create a DRAFT invoice.

        `note` is payer-visible — PayPal renders it as "Note from seller" — so the agreed
        scope and cap live there, where the client can read them. `terms` is the full clause
        list, carried in `detail.terms_and_conditions`, so the exclusion a billed line cites is
        on the same page as the line.
        A recipient is optional: `invoice.required` is `["detail"]` only.
        """
        body: dict[str, Any] = {
            "detail": {
                "currency_code": currency,
                "invoice_date": invoice_date,
                "reference": reference[:120],
                "note": note[:4000],
                "payment_term": {"term_type": term_type},
            },
            "invoicer": {"business_name": invoicer_name},
            "items": [i.to_paypal() for i in items],
        }
        if terms:
            # Payer-visible and separate from `note`: PayPal renders it under its own heading,
            # so the full clause list does not have to be squeezed into a one-line summary.
            if len(terms) > TERMS_LIMIT:
                # Silently clipping here would take the clause a billed line cites off the
                # client's page, with no error anywhere. An engagement with enough scope to
                # overflow 4000 characters is exactly the kind that gets disputed.
                raise ValueError(
                    f"terms_and_conditions is {len(terms)} characters; PayPal accepts "
                    f"{TERMS_LIMIT}. Shorten the clause list rather than letting the payer "
                    f"lose the end of it."
                )
            body["detail"]["terms_and_conditions"] = terms
        if recipient_email:
            body["primary_recipients"] = [{"billing_info": {"email_address": recipient_email}}]
        return self.c.request(
            "POST", "/v2/invoicing/invoices", json_body=body, idempotency=f"create-{reference}"
        )

    def send(self, invoice_id: str, *, notify: bool = False) -> dict[str, Any]:
        """Move DRAFT to payable. With notify=False no email is sent and it lands on UNPAID."""
        return self.c.request(
            "POST",
            f"/v2/invoicing/invoices/{invoice_id}/send",
            json_body={"send_to_recipient": notify, "send_to_invoicer": False},
        )

    def get(self, invoice_id: str) -> dict[str, Any]:
        return self.c.request("GET", f"/v2/invoicing/invoices/{invoice_id}")

    # -- the mechanism ------------------------------------------------------

    def add_items(
        self,
        invoice_id: str,
        new_items: Iterable[LineItem],
        *,
        notify: bool = True,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Append line items to an invoice that has already been sent.

        PUT is a full-document replace — there are no partial updates — so the current
        invoice is read, the readOnly and server-computed fields are dropped, and `amount`
        is reduced to its currency so PayPal recomputes the total itself. Echoing back the
        `amount.value` you just read is what produces 400 `calculation_error`.

        notify=True asks PayPal to email the client that the invoice changed. That is the
        consent step, and it is PayPal's own machinery rather than something we invented.
        """
        with _lock_for(invoice_id):
            return self._add_items_locked(invoice_id, new_items, notify, idempotency_key)

    def _add_items_locked(
        self,
        invoice_id: str,
        new_items: Iterable[LineItem],
        notify: bool,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        new = list(new_items)
        current = self.get(invoice_id)
        items = list(current.get("items", [])) + [i.to_paypal() for i in new]
        if len(items) > MAX_ITEMS:
            raise ValueError(
                f"{len(items)} line items; PayPal accepts {MAX_ITEMS}. A long engagement has "
                f"to consolidate billed extras rather than discovering this at the hundredth."
            )

        upd = {k: v for k, v in current.items() if k not in READONLY + COMPUTED}
        upd["items"] = items
        upd["amount"] = {"currency_code": current["detail"]["currency_code"]}

        # Derived from what is being ADDED, never from the resulting document. Hashing the
        # result means a retry after a lost response reads a longer invoice and produces a
        # different digest. Callers that know the originating events pass their ids instead,
        # so the key stays stable even if the line text is later reworded.
        #
        # None of which PayPal honours. Verified live on 2026-10-15: the identical PUT sent
        # twice with the same PayPal-Request-Id took a sandbox invoice from $225.00 to
        # $250.00. The header is documented for POST and does not appear in the invoice PUT
        # reference at all. It is still sent — it costs nothing and may one day work — but
        # the guard against double-billing is the ledger in cli.py and web.py, not this.
        # See docs/UPSTREAM.md.
        if idempotency_key is None:
            idempotency_key = hashlib.sha256(
                "".join(i.display_name for i in new).encode()
            ).hexdigest()[:16]
        return self.c.request(
            "PUT",
            f"/v2/invoicing/invoices/{invoice_id}",
            json_body=upd,
            params={"send_to_recipient": str(notify).lower(), "send_to_invoicer": "false"},
            idempotency=f"items-{invoice_id}-{idempotency_key}",
        )

    def reconcile(self, invoice_id: str, billed: Iterable[str]) -> tuple[list[str], list[str]]:
        """Compare the ledger against the live invoice, in both directions and by count.

        The detection half of the concurrency problem. Locks serialise writers inside one
        process; two processes growing one invoice cannot be serialised from here, because
        PayPal offers nothing to do it with. So the two records are compared afterwards.

        Returns (missing, unexplained):

        * **missing** — the ledger says it was billed and the invoice does not carry it. This
          is the lost write: the client is undercharged and nobody was told.
        * **unexplained** — the invoice carries a line the ledger does not justify. This is the
          double charge, and it is the worse of the two. A first version of this looked only
          for missing lines, so an invoice billing the same work twice was reported green.

        Counted rather than set-compared, because the opening line and any two same-day events
        with no description share a display name. Against a set, one of two identical lines
        vanishing is invisible — which is exactly the failure this is for.
        """
        live = Counter(i.get("name", "") for i in self.get(invoice_id).get("items", []))
        expected = Counter(billed)
        missing = sorted((expected - live).elements())
        unexplained = sorted((live - expected).elements())
        return missing, unexplained

    # -- payer surface ------------------------------------------------------

    def payer_url(self, invoice_id: str) -> str:
        """Derivable from the id. There is no `payer-view` link rel on the invoice object;
        the links are self, replace, cancel, remind, record-payment and qr-code."""
        host = "www.sandbox.paypal.com" if "sandbox" in self.c.s.base_url else "www.paypal.com"
        return f"https://{host}/invoice/payerView/details/{invoice_id}?qr=1"

    def record_payment(
        self,
        invoice_id: str,
        *,
        amount: Decimal,
        currency: str = "USD",
        method: str = "BANK_TRANSFER",
        when: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Record money that arrived outside PayPal, so the invoice stops asking for it.

        Contractors get paid by bank transfer constantly. Without this the client pays, the
        invoice stays UNPAID, and the next discovered line is added to a bill that looks
        unpaid to everyone who opens it — the one place this product cannot afford to be wrong.

        Verified live: a $40.00 BANK_TRANSFER against a $100.00 invoice moves it to
        PARTIALLY_PAID with $60.00 due, and a later item written by `add_items` raises the
        total to $125.00 with $85.00 due. The recorded payment survives the write.
        """
        body: dict[str, Any] = {
            "method": method,
            "payment_date": when,
            "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
        }
        if note:
            body["note"] = note[:2000]
        return self.c.request(
            "POST", f"/v2/invoicing/invoices/{invoice_id}/payments", json_body=body
        )

    def qr_png(self, invoice_id: str, *, size: int = 500) -> bytes:
        """The QR the client files on day one.

        `generate-qr-code` returns multipart/form-data, not image/png: the PNG arrives as
        base64 text in a part named "image" whose own Content-Type is text/plain.
        """
        payload = self.c.request(
            "POST",
            f"/v2/invoicing/invoices/{invoice_id}/generate-qr-code",
            json_body={"width": size, "height": size, "action": "pay"},
            raw=True,
        )
        raw = bytes.fromhex(payload["_raw_b64"])
        if b"multipart" in payload.get("_ct", "").encode() or raw.lstrip().startswith(b"--"):
            part = raw.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0].strip()
            return base64.b64decode(part)
        return raw


def total_of(invoice: dict[str, Any]) -> Decimal:
    return Decimal((invoice.get("amount") or {}).get("value", "0"))
