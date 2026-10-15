// The tools the assistant may call.
//
// Three read-only client tools, and exactly one that moves money. The mutating one is
// `kind: 'server'`: Studio advertises its schema and never executes it, so the call is run by
// our own Next route against the Python service. A PayPal credential has no business in a
// browser bundle, and this is the structural way to say so rather than a comment claiming it.

import type { AgAiParamsBuilder, AgAiTool, AgStudioApi } from 'ag-studio';

type Api = AgStudioApi;

async function backend<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend${path}`, { cache: 'no-store', ...init });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export function unloggedTools(api: Api): AgAiTool[] {
  return [
    api.defineAiTool({
      name: 'read_engagement',
      description:
        'The agreed scope of this engagement: every clause verbatim, the rate card, and the cap ' +
        'stated to the client. Read this before judging whether any work falls inside or outside.',
      params: (s: AgAiParamsBuilder) => s.object({}),
      async execute(_args, ctx) {
        return ctx.success(await backend('/api/engagement'));
      },
    }),

    api.defineAiTool({
      name: 'read_verdicts',
      description:
        'How each work event was placed against the scope: included, billable_extra, ' +
        'scope_request, or noise, with the clause it relied on and the span of text that decided ' +
        'it. A row with no clause_id was not auditable and should be treated as suspect.',
      params: (s: AgAiParamsBuilder) => s.object({}),
      async execute(_args, ctx) {
        return ctx.success(await backend('/api/verdicts'));
      },
    }),

    api.defineAiTool({
      name: 'read_invoice_changes',
      description:
        'The append-only record of every line this system has already added to the live PayPal ' +
        'invoice, with the running total after each one. Check this before proposing anything, ' +
        'so the same work is not billed twice.',
      params: (s: AgAiParamsBuilder) => s.object({}),
      async execute(_args, ctx) {
        return ctx.success(await backend('/api/ledger'));
      },
    }),

    // The only tool that changes what a client owes.
    api.defineAiTool({
      name: 'add_billable_work',
      kind: 'server',
      description:
        'Itemise the named billable extras onto the live PayPal invoice. The invoice id, the ' +
        'payer link and the QR stay valid, and PayPal emails the client that it changed. Only ' +
        'events already adjudicated as billable_extra are accepted; anything else is refused. ' +
        'This moves real money, so say what you are adding and why before calling it.',
      params: (s: AgAiParamsBuilder) =>
        s.object({
          invoice_id: s.string(),
          event_ids: s.array(s.string()),
        }),
    }),
  ];
}
