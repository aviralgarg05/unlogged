"""The live half of scripts/verify.py, run inside the project's environment.

Emits tab-separated CHECK lines so the caller can render them alongside its own. Not meant to
be run directly, though it works if you do.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

from unlogged.config import Settings
from unlogged.paypal import Invoices, LineItem, PayPalClient
from unlogged.paypal.invoices import total_of


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
                reference=f"verify-{date.today().isoformat()}",
                note="Agreed scope: checkout page. Cap USD 1,200.00.",
                invoice_date=date.today().isoformat(),
            )
            iid = created["id"]
            inv.send(iid, notify=False)
            before = total_of(inv.get(iid))

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
            print(f"PAYER\t{inv.payer_url(iid)}")
    except Exception as e:  # a live failure is a result, not a crash
        emit("live mechanism", "FAIL", str(e)[:60])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
