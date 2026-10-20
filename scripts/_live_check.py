"""The live half of scripts/verify.py, run inside the project's environment.

Emits tab-separated CHECK lines so the caller can render them alongside its own. Not meant to
be run directly, though it works if you do.
"""

from __future__ import annotations

import os
from decimal import Decimal

from unlogged.config import Settings
from unlogged.paypal import Invoices, LineItem, PayPalClient
from unlogged.paypal.invoices import today, total_of


def emit(name: str, status: str, detail: str) -> None:
    print(f"CHECK\t{name}\t{status}\t{detail}")


def main() -> int:
    os.environ["UNLOGGED_REPLAY"] = "0"
    try:
        with PayPalClient(Settings.from_env()) as c:
            inv = Invoices(c)
            created = inv.create(
                items=[LineItem("Agreed scope", Decimal("8"), Decimal("65.00"))],
                invoicer_name="Aviral Garg",
                recipient_email=None,
                reference=f"verify-{today().isoformat()}",
                note="Agreed scope: checkout page. Cap USD 1,200.00.",
                invoice_date=today().isoformat(),
            )
            iid = created["id"]
            inv.send(iid, notify=False)
            before = total_of(inv.get(iid))
            # Captured BEFORE the write, so the claim can be compared rather than asserted.
            # The payer link and the QR are the whole promise — "same invoice, same link, same
            # QR" — and the live run printed the link without ever checking it had not moved,
            # while PayPal's own documentation says nothing about either surviving an update.
            payer_before = inv.payer_url(iid)
            qr_before = inv.qr_png(iid)

            inv.add_items(
                iid,
                [
                    LineItem(
                        "Retry logic",
                        Decimal("2"),
                        Decimal("85.00"),
                        provenance="github 03 Oct",
                    )
                ],
                notify=False,
            )
            after = inv.get(iid)
            total_after = total_of(after)
            png = inv.qr_png(iid)

            emit(
                "a sent invoice grows line items",
                "PASS" if total_after > before else "FAIL",
                f"${before} -> ${total_after}",
            )
            emit(
                "the invoice id survives the write",
                "PASS" if after["id"] == iid else "FAIL",
                iid,
            )
            emit(
                "the item is named on PayPal's own object",
                "PASS" if any("github 03 Oct" in i["name"] for i in after["items"]) else "FAIL",
                f"{len(after['items'])} items",
            )
            emit(
                "the QR still generates for the same invoice",
                "PASS" if png[:4] == b"\x89PNG" else "FAIL",
                f"{len(png)} byte PNG",
            )
            payer_after = inv.payer_url(iid)
            emit(
                "the payer link the client filed still resolves to this invoice",
                "PASS" if payer_after == payer_before else "FAIL",
                "unchanged" if payer_after == payer_before else f"{payer_before} -> {payer_after}",
            )
            emit(
                "the QR is byte-identical to the one generated before the write",
                "PASS" if png == qr_before else "FAIL",
                "identical" if png == qr_before else f"{len(qr_before)} -> {len(png)} bytes",
            )
            # Money that arrived by bank transfer, recorded so the invoice stops asking for
            # it — and then a further discovered line written on top of it. If the write
            # dropped the payment, the client would be asked twice for money they had sent.
            paid = inv.record_payment(
                iid,
                amount=Decimal("100.00"),
                when=today().isoformat(),
                note="Bank transfer, reference NW-0042",
            )
            after_pay = inv.get(iid)
            due_before = after_pay["due_amount"]["value"]
            inv.add_items(
                iid,
                [LineItem("Late discovery", Decimal("1"), Decimal("85.00"))],
                notify=False,
            )
            final = inv.get(iid)
            kept = Decimal(final["payments"]["paid_amount"]["value"]) >= Decimal("100.00")

            emit(
                "an out-of-band payment is recorded against the invoice",
                "PASS" if paid.get("payment_id") else "FAIL",
                f"{after_pay['status']}, {due_before} due",
            )
            emit(
                "a later line does not discard the recorded payment",
                "PASS" if kept else "FAIL",
                f"paid {final['payments']['paid_amount']['value']}, "
                f"due {final['due_amount']['value']}",
            )

            print(f"PAYER\t{inv.payer_url(iid)}")
    except Exception as e:  # a live failure is a result, not a crash
        emit("live mechanism", "FAIL", str(e)[:60])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
