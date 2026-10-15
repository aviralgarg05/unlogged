> **Note.** This records the verification run that opened the project, when the mechanism
> under test was `invoice_discount`. That mechanism works, but the product does not use it:
> a discount is the wrong semantics for billing work that was done, and on camera it is a
> number going down. What shipped instead is **appending line items to a sent invoice** —
> same stable id and QR, money going up, each line named with its provenance. The API
> findings below (full-document PUT, the readOnly set, the QR multipart, the broken
> conditional-rules path) all still hold and are what the engine is built on.

# Pre-build verification — 2026-10-15

Everything below was checked directly against primary sources rather than taken from research
summaries. Done before writing any product code, so the day-1 gate fails only for real reasons.

## PayPal Invoicing v2 schema

Source: `developer.paypal.com/api/invoicing/v2/schema.json`, HTTP 200, **557,403 bytes**, 132 schemas.

| Claim | Result |
|---|---|
| `invoice.required` is `["detail"]` only → a recipient-less invoice is legal | **CONFIRMED** |
| `detail.payment_term.conditional_rules` → `payment_term_conditional_rules`, **not** readOnly | **CONFIRMED** |
| `early_payment_discount` = `{discount_end_date, percent, amount, is_applied}` | **CONFIRMED** |
| `POST /conditional-rules` body (`conditional_rules`) has only `rules` (readOnly, maxItems 5) + `links` (readOnly) | **CONFIRMED — no writable payload in the published spec** |
| `SHARED` is a real member of the 16-value `invoice_status` enum | **CONFIRMED** |
| `percentage` is a string matching `^((-?[0-9]+)\|(-?([0-9]+)?[.][0-9]+))$` → `"20"` and `"40"` are valid | **CONFIRMED** |
| `qr_config` = width/height 150–500 (default 500), `action` default `pay` | **CONFIRMED** |
| `PUT /invoices/{invoice_id}` query params `send_to_recipient` / `send_to_invoicer` **default to `true`** | **CONFIRMED — must pass false explicitly** |
| `effective_due_amount` and `effective_invoice_total` exist on the `invoice` object | **CONFIRMED** |
| Link rel for the hosted payer page is `payer-view` | **CONFIRMED** |

**Three corrections to the research**, all now applied to `day1_probe.py`:

1. **Only three** top-level invoice properties are readOnly — `id`, `parent_id`, `links`. The claim of
   six was wrong: `status`, `due_amount` and `gratuity` are **not** readOnly. The full-document PUT
   strips the real three, and strips server-computed fields only after a 422.
2. The discounted figure to read is **`effective_due_amount`**, not `due_amount` (which is the
   pre-discount value). The probe reads effective first.
3. `POST /v2/invoicing/invoices` returns a minimal body unless **`Prefer: return=representation`**
   is sent, so the id would otherwise have to be scraped from the `Location` header. Header added.

**Conclusion.** The mechanic is sound on paper. The inline discount path is writable, the QR route is
real, and the no-email `SHARED` flow is PayPal's own documented behaviour. The one thing the schema
cannot tell us is whether the **hosted payer page actually charges the moved amount** — that is check
6, it needs human eyes, and it is the only check that can kill the concept.

## AG Studio licensing — the sponsor-play risk, resolved

`ag-studio@3.0.0` and `ag-studio-react@3.0.0` are `license: "Commercial"` and ship an AG Grid EULA
(v39, dated 2026-05-11) as `LICENSE.html`. The EULA's trial clause 4.2 caps a trial at **60 days**
and 4.2(d) expressly permits the software to *"function for a limited period of time"*. That is the
trap: any trial key taken out in October expires during the Dec 1–15 judging window.

Verified in the shipped bundle (`dist/package/main.cjs.js`) rather than assumed:

```js
isDisplayWatermark() {
  const eDocument = this.document;
  return isForceWatermark(eDocument)
      || !isLocalhost(eDocument) && !isWebsiteUrl(eDocument) && !!this.watermarkMessage?.length;
}
```

And `validateLicense()` branches over `missing`, `expired`, `!valid` and `isTrial && trialExpired` —
**every branch only ever sets `watermarkMessage`.** No branch disables a feature or gates behaviour.

**Therefore: no licence key + localhost = full functionality, no watermark, and nothing that can
expire, because no key exists to expire.** Accepting a trial key is strictly worse than declining
one — a trial key *can* reach `trialExpired`, while the keyless path cannot.

Caveat for a hosted demo: off localhost the `missing` branch sets a watermark message. Cosmetic only,
never functional. The judge path is `git clone` → localhost, so this does not bite.

## Official PayPal boilerplate

`paypaldev/hackathon-paypal-ag-grid-boilerplate` exists, pushed 2026-10-12, 3 stars. Stack confirmed
exactly as researched: `ag-studio@3.0.0`, `ag-studio-react@3.0.0`, `ag-grid-community@36.2.0`,
`next@16.3.6`, `react@19.2.8`.

**Note: the boilerplate itself has no LICENSE file** (`licenseInfo: null`). The hackathon requires a
detectable open-source licence visible in our repo's About section, so we add our own — and we must
never vendor ag-studio's source, only depend on the npm package.

## Competitive check — the lane is empty

| Query, repos created since 2026-09-30 | Hits |
|---|---|
| `paypal food waste` | **0** |
| `paypal surplus food` | **0** |
| `paypal bakery` | **0** |
| `food waste agent paypal` | **0** |
| `markdown pricing paypal` | **0** |

The surplus-food repos the research flagged as a naming collision are all **unrelated to this
hackathon**: `tranhoangtrvng/LastBite` is a Vietnamese web-programming assignment,
`Tshimologo-tm/LastBite` is a Java Android pantry manager, `reenu153/LastBite---Surplus-Food-MarketPlace`
is a Too Good To Go clone backend, `ahlawatansh/LastPlate` is a food-delivery platform. None mentions
PayPal.

`ahlawatansh/LastPlate` is worth one line in the README as adjacent prior art — it does ML demand
forecasting with "dynamic closing clearance pricing" — but it is a delivery marketplace with no
payment-rail mechanism, no vision decomposition and no PayPal.

**Open issue: the name.** "shelfmark" is a library-cataloguing term and already has ~6 GitHub repos
created in October 2026 alone (`gandolh/shelfmark` on Oct 14, `dylanisom1-lgtm/shelfmark` Oct 13).
None is a competitor, but it is bad for discoverability and reads as convergence. Worth renaming.

---

# Day-1 gate: **GREEN** — run live against sandbox, 2026-10-15

5/5 automated checks plus the manual payer-page check. `uv run day1_probe.py` reproduces it.
Raw request and response bodies in `DAY1.md`.

**The concept is alive.** A PayPal invoice's charged amount really does move while its printed QR
stays valid — £3.00 → £2.00 → £1.00 across two writes, invoice id stable, QR never reprinted. The
hosted payer page reached from the original QR charged **£1.00** against a £4.00 list price.

## The mechanism changed, and the new one is better

**`early_payment_discount` does not work and must be abandoned.** It is accepted with HTTP 201 and
then **silently dropped** — no error, no warning, `effective_due_amount` left null. Tested four ways:
`DUE_ON_RECEIPT`, `NET_30`, and `DUE_ON_DATE_SPECIFIED` with a due date a week out, and with
`discount_end_date` both today and future. `conditional_rules` never survived a single create.
`POST /conditional-rules` returns **HTTP 500**, exactly as the published schema predicts (its only
non-`links` property is `readOnly`, so there is no writable payload) and exactly as a competitor
reported. Both routes are dead. This also means the research's fallback plan was itself unavailable —
you cannot `PUT` a conditional rule that cannot be created.

**What works instead:** `amount.breakdown.discount.invoice_discount.percent`, a plain percentage
with no date semantics at all. PayPal persists it and computes the money itself (£4.00 at 25% →
a -£1.00 discount line and a £3.00 total).

This is **strictly better for the product** than the original design. The brief had to fight
`discount_end_date`'s day-granularity to get intra-hour movement; a plain percentage has no date in
it, so the markdown ladder is just a sequence of percentages and the whole awkwardness disappears.

## Three traps worth writing down

1. **The full-document PUT fails with 400 `calculation_error` on `/amount/value` if you echo back
   the amount you just read.** PayPal recomputes the total from the breakdown, so send
   `currency_code` plus the breakdown only. This is the single most likely thing to cost someone a
   day, and nothing in the docs says it.
2. **`generate-qr-code` returns `multipart/form-data`, not `image/png`.** The PNG is base64 text
   inside a part named `image` whose own Content-Type is `text/plain`. A naive content-type check
   rejects a perfectly good response.
3. **Silent send lands on `UNPAID`, not `SHARED`.** `SHARED` is a real enum member but is not what
   `send_to_recipient:false, send_to_invoicer:false` produces. The invoice is payable either way and
   no email is sent, so the flow is fine — but assert on the right status.

## Two free wins

- **The QR URL is derivable from the invoice id**: `https://www.sandbox.paypal.com/invoice/payerView/details/{INVOICE_ID}?qr=1`.
  There is no `payer-view` link rel on the invoice (the links are `self`, `replace`, `cancel`,
  `remind`, `record-payment`, `qr-code`), but the QR decodes to that pattern, so the payer page can
  be reconstructed without re-calling the QR endpoint.
- **PayPal's own payer page renders the markdown**, which the brief listed as an open question
  hoping for a second proof shot. It shows `Subtotal £4.00` / `Discount (75% off) -£3.00` /
  `Total £1.00`. The strike-through is free, on PayPal's own hosted page, in the video.
