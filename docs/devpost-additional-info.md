# Devpost — "Additional info"

One block per field. Everything here is checked against the repository; the three marked
**your call** are judgement or eligibility and nobody can answer them for you.

---

## Explain how your project meets the main technology requirement

> **PayPal — Invoicing v2 (sandbox), called directly over `httpx`.** The whole product is one
> invoice that grows. `POST /v2/invoicing/invoices` opens the engagement's single invoice,
> `/send` makes it payable, and `PUT /v2/invoicing/invoices/{id}` adds each discovered billable
> line to that same already-sent invoice — the id, the payer link and the QR survive, which is
> the mechanism everything else rests on. Also used: `/generate-qr-code`, `POST /{id}/payments`
> to record money that arrived out of band, and `GET` for reconciliation.
>
> **PayPal — Webhooks with signature verification.** `/v1/notifications/verify-webhook-signature`,
> verified over the raw request bytes, because re-serialising the parsed JSON changes the payload
> and fails verification for reasons that look like a signing bug.
>
> **PayPal — Server SDK (APIMatic-generated).** `payments.get_captured_payment` and its
> `seller_receivable_breakdown`, which answers the question a cross-border contractor actually
> ends on: not "did they pay" but "how much reached me". Invoicing goes over httpx because that
> SDK ships no invoicing controller.
>
> **AI — `gpt-6.1-sol`, OpenAI Responses API with a strict JSON schema.** The adjudicator. Given
> the engagement's scope clauses and the work events, it decides which side of the agreed line
> each event falls on, and it must name the clause it relied on and quote the span of text that
> decided it. A verdict citing a clause the engagement does not have, or quoting words the event
> does not contain, is refused before it can reach an invoice.
>
> **AI — `gpt-5.4-mini`.** The AG Studio dashboard assistant, which reads the scope, the
> adjudications and the ledger, and can itemise approved extras onto the live invoice through a
> server-executed tool — so the PayPal credential never enters the browser bundle.

## Which additional sponsor tool(s) did you use?

Tick **AG Grid** and **APIMatic**. Nothing else.

- **AG Grid** — `ag-studio@3.0.0` + `ag-grid-community@36.2.0`, the dashboard, with a custom
  Evidence widget registered into the registry.
- **APIMatic** — `paypal-server-sdk@2.4.0` in `src/unlogged/paypal/settlement.py`.

Do **not** tick Render. `render.yaml` is written and has never been deployed, and `HONESTY.md`
says so. Claiming a sponsor you did not run is the one thing in this form that can only cost you.

## Public code repository

```
https://github.com/aviralgarg05/unlogged
```

MIT licence, README with setup instructions, and a section explaining exactly how PayPal and the
model are used. **Must be public before you paste this.**

## URL to a working demo, hosted application or test build

```
https://www.sandbox.paypal.com/invoice/payerView/details/INV2-DP6S-XFGQ-67JW-TMQL?qr=1
```

> The live sandbox invoice this project produced: $520.00 of agreed scope plus two discovered
> lines, $902.50, each naming the pull request it came from. There is no hosted application —
> the repository runs both halves locally in one command, and reproduces the entire flow with
> no credentials of any kind. See the testing instructions.

## Testing instructions

> Nothing is needed — no PayPal account, no API key.
>
> ```
> git clone https://github.com/aviralgarg05/unlogged && cd unlogged
> uv sync
> uv run scripts/verify.py
> ```
>
> 16 checks, about twenty seconds. It runs the test suite, reproduces the evaluation to the
> cent, replays the full apply flow from 305 committed PayPal exchanges — ending at
> `Total now USD 902.50` — and checks the submission requirements.
>
> The dashboard, both halves, still with no credentials:
>
> ```
> docker compose up        # dashboard on :3000/dashboard, API on :8000
> ```
>
> With your own PayPal sandbox credentials in `.env`, `uv run scripts/verify.py --live` re-proves
> the central claim against PayPal on the day you run it: it creates a real invoice, grows it,
> records a bank transfer against it, grows it again, and prints the payer URL. A date in a
> README is worth less than a command.

## How would you rate your overall experience integrating PayPal? (1–10)

**Your call.** For what it is worth: the Invoicing API does something genuinely valuable that
nothing else on the rails does, and the documentation does not mention it.

## Overall experience rating — why

> Invoicing v2 can do something I have not found on another payment rail: an invoice that has
> already been sent can grow line items while its id, its payer URL and its QR stay valid. That
> is the entire product, and it is in no documentation I could find — I established it by trying
> it, and the live check now captures the payer link and the QR before the write and compares
> after, because the reference does not say either survives. They do; the QR comes back
> byte-identical.
>
> The sandbox is genuinely free and genuinely complete, which made a no-credentials demo
> possible.
>
> Six things cost me a day each and are written up with reproductions in `docs/UPSTREAM.md`:
>
> 1. `early_payment_discount` is accepted with **201 and silently dropped** — four term/date
>    combinations, created, sent and re-read fresh, absent every time. `POST /conditional-rules`
>    returns **500** for every payload shape its own spec suggests. The agent toolkit's
>    `PROMPTS.md` documents only that path, so an agent following the shipped guidance writes a
>    discount, is told it worked, and charges the customer full price.
> 2. **`PayPal-Request-Id` is accepted on an invoice `PUT` and ignored.** The identical write
>    twice under one key took a sandbox invoice from $225.00 to $250.00. No ETag, no `If-Match`
>    either, so two writers that both read first lose a line with no error.
> 3. `generate-qr-code` returns a **base64 multipart envelope**, not an image.
> 4. The APIMatic-generated Server SDK ships **no invoicing controller** — six controllers, none
>    of them invoicing.
> 5. **`send` blames a missing recipient when the invoice date is the problem.** A future
>    `invoice_date` silently makes the send *scheduled*; without a recipient it is refused with
>    `MISSING_RECIPIENT_EMAIL`, naming the one field that is not the cause. Follow the error, add
>    a recipient, and the 422 becomes a 202 and an invoice the client cannot pay.
> 6. Only **three** top-level invoice properties are readOnly, not the six commonly assumed, and
>    `PUT` 400s on `calculation_error` if you echo back the `amount.value` you just read.
>
> Every one of those reproduces from the repository.

## Are you open to being contacted for feedback?

**Your call.** Six reproducible defect reports are already written; saying yes is the cheapest
way for them to reach someone.

## If you used the APIMatic Context Plugin — your experience

> I used the APIMatic-generated `paypal-server-sdk` (2.4.0) rather than the Context Plugin
> itself. The thing worth reporting: the SDK ships six controllers — `o_auth_authorization`,
> `orders`, `payments`, `subscriptions`, `transaction_search`, `vault` — and **no invoicing
> controller**. Enumerated directly, not inferred from documentation.
>
> That matters more than a missing endpoint usually would, because the premise is that an agent
> asking "how do I do X with the PayPal SDK" gets a grounded answer rather than a remembered one.
> For anything invoicing-shaped the grounded answer is *you cannot with this SDK* — correct, but
> an agent that does not ask will reach for a controller that is not there. Invoicing v2 is a
> large, self-serve, live surface and, going by this hackathon's field, one of the most commonly
> reached-for parts of the platform.
>
> So this project uses the SDK for what it does cover — `payments.get_captured_payment` and
> `seller_receivable_breakdown` — and calls Invoicing v2 over httpx because it has to. That
> division is stated in the README rather than blurred.

## If you used AG Grid — your experience

> AG Studio 3.0.0, with one deliberate departure from the boilerplate. The boilerplate hands
> Studio a fully-materialised array and lets the engine filter, sort and page in the browser.
> This declares `capabilities: { pagination, filter, sort }`, so the engine forwards the window,
> the filter tree and the sort order to `getData` and the rows stay in the Python service.
> Honouring that is a contract, not a hint — an operator the service cannot apply is refused
> rather than returning unfiltered rows under a filter the reader set.
>
> A custom Evidence widget is registered into the registry, and the one tool that moves money is
> executed server-side so a PayPal credential never enters the browser bundle.
>
> One defect worth reporting: **a public custom widget cannot declare `formatShape`.** The docs
> say the shape is required for AI and that it must be built with a shape builder — but
> `AgFormatShapeParams` is `{ api, context }` and `ag-studio` exports no builder at all (50
> runtime exports, none shape-related). Probed at runtime, the params object carries a
> `Symbol(ag.internal)` that presumably holds it, which is private. Returning a plain object
> instead throws `formatShape.parse is not a function` inside `hydrateWidget` and takes the whole
> dashboard down. The cost is bounded — the agent can still place the widget and map its fields —
> but it cannot configure the widget's format.

## Which AI tools have you leveraged while working on this project?

> `gpt-6.1-sol` (OpenAI Responses API, strict JSON schema, function calling) as the adjudicator
> that decides what reaches an invoice, and `gpt-5.4-mini` as the AG Studio dashboard assistant.

## Level of learning · AI value for your career · the three eligibility boxes

**Your call** — and the eligibility ones are declarations only you can make.
