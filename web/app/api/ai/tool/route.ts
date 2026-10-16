import { sameOrigin, withinRate } from '@/lib/relay-guard';
// Executes a `kind: 'server'` tool call. The browser may ask for this, but the PayPal
// credential and the decision about what is billable both stay behind it.

import { runServerTool } from '@/lib/server-tools';

export async function POST(request: Request) {
  // This route spends the owner's OpenAI credit and takes no credential, because the caller is
  // a browser. Two bounds rather than none: see lib/relay-guard.ts for why that is the trade.
  if (!sameOrigin(request)) return Response.json({ error: { message: 'Cross-origin requests are not accepted.' } }, { status: 403 });
  if (!withinRate(request)) return Response.json({ error: { message: 'Too many requests. Wait a minute.' } }, { status: 429 });

  let body: { name?: unknown; arguments?: unknown };
  try {
    body = await request.json();
  } catch {
    return Response.json({ ok: false, error: 'body must be JSON' }, { status: 400 });
  }
  if (typeof body.name !== 'string') {
    return Response.json({ ok: false, error: 'name is required' }, { status: 400 });
  }
  const result = await runServerTool({
    name: body.name,
    arguments: (body.arguments ?? {}) as Record<string, unknown>,
  });
  return Response.json(result, { status: result.ok ? 200 : 400 });
}
