// Executes a `kind: 'server'` tool call. The browser may ask for this, but the PayPal
// credential and the decision about what is billable both stay behind it.

import { runServerTool } from '@/lib/server-tools';

export async function POST(request: Request) {
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
