// The tools the assistant may call.
//
// Three read-only client tools, and exactly one that moves money. The mutating one is executed
// by our own Next route against the Python service, so a PayPal credential never enters a
// browser bundle — the browser can only ask the server to run a named tool, and the route
// validates the name and the arguments before anything reaches the money path.
//
// It was declared `kind: 'server'`, which was decorative. In `ag-studio@3.0.0` that kind
// builds a tool with a schema and `execute: undefined` — the library advertises it to the
// model and leaves execution to the host, and there is no hook anywhere in the bundle that
// hands the call back. The host here never executed it: `/api/ai/tool` was written for
// exactly this and nothing in the repository called it. So the one tool that moves money was
// offered to the model and could not run, which on the headline AG Studio differentiator is
// worse than not offering it. It is declared normally now and its `execute` is the
// round-trip to that route. The credential boundary is where it always was — in the route,
// not in the word.

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
      async execute(args, ctx) {
        // Our own route, not the Python service: it holds the allowlist of tools the browser
        // may ask for, and it is the only side of this that can reach a PayPal credential.
        const res = await fetch('/api/ai/tool', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ name: 'add_billable_work', arguments: args }),
        });
        const body = (await res.json().catch(() => null)) as
          | { ok?: boolean; data?: unknown; error?: string }
          | null;
        if (!res.ok || !body?.ok) {
          // Surfaced, never swallowed. A refusal the model is not told about becomes a
          // confident reply that the client's invoice changed when it did not.
          return ctx.error(body?.error ?? `add_billable_work failed (${res.status})`);
        }
        return ctx.success(JSON.stringify(body.data), body.data);
      },
    }),
  ];
}
