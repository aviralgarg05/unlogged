// Execution for the tools declared `kind: 'server'`.
//
// Studio advertises those schemas and never runs them — that is what the kind means — so the
// execution lives here, on the server, next to the only process that holds a PayPal credential.
// Written as a pure function over a fetch so it can be tested without a network or a model.

// Imported relatively, not through the `@/lib` alias, so this module stays unit-testable under
// plain node with no bundler. It used to carry its own copy of the default, which is two
// places for one fact.
import { backendOrigin } from './backend-origin.ts';

const BACKEND = backendOrigin(process.env.UNLOGGED_API);

export type ServerToolCall = { name: string; arguments: Record<string, unknown> };

export type ServerToolResult =
  | { ok: true; data: unknown }
  | { ok: false; error: string };

/** The only server tool. Anything else is refused rather than guessed at. */
export const SERVER_TOOLS = ['add_billable_work'] as const;

export function isServerTool(name: string): boolean {
  return (SERVER_TOOLS as readonly string[]).includes(name);
}

function invalid(call: ServerToolCall): string | null {
  const { invoice_id, event_ids } = call.arguments as {
    invoice_id?: unknown;
    event_ids?: unknown;
  };
  if (typeof invoice_id !== 'string' || !invoice_id.trim()) {
    return 'invoice_id must be a non-empty string';
  }
  if (!Array.isArray(event_ids) || event_ids.length === 0) {
    return 'event_ids must be a non-empty array';
  }
  if (!event_ids.every((id) => typeof id === 'string')) {
    return 'event_ids must contain only strings';
  }
  return null;
}

/**
 * Run a server tool call.
 *
 * The backend is the authority on what is billable: it re-adjudicates and refuses anything that
 * is not already a billable extra. This does not re-check that, deliberately — two places
 * deciding what may be billed is how they drift apart.
 */
export async function runServerTool(
  call: ServerToolCall,
  fetchImpl: typeof fetch = fetch,
): Promise<ServerToolResult> {
  if (!isServerTool(call.name)) {
    return { ok: false, error: `${call.name} is not a server tool` };
  }
  const bad = invalid(call);
  if (bad) return { ok: false, error: bad };

  const res = await fetchImpl(`${BACKEND}/api/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...call.arguments, notify: true }),
  });
  const text = await res.text();
  if (!res.ok) return { ok: false, error: `backend refused: ${res.status} ${text.slice(0, 300)}` };
  try {
    return { ok: true, data: JSON.parse(text) };
  } catch {
    return { ok: false, error: 'backend returned a non-JSON body' };
  }
}
