// Proxy to the Python service. Keeps the backend off the public internet in a deployment and
// gives the browser a same-origin endpoint.
//
// Which means that in such a deployment THIS is the public internet, and it forwarded any path
// a caller named — including POST — straight through. The service it fronts moves money. So the
// proxy carries an explicit list of what the dashboard actually calls, and nothing else gets
// through: a route that forwards everything is not a proxy, it is a hole with a fetch in it.

import { BACKEND } from '@/lib/backend';

// Read paths the dashboard's data sources and tools use.
const READABLE = new Set([
  'api/engagement',
  'api/events',
  'api/verdicts',
  'api/ledger',
  'api/telemetry',
  'health',
]);

// The only path that changes anything. POST reaches this and nothing else — notably not
// /webhook, whose whole job is to be called by PayPal rather than by a browser.
const WRITABLE = new Set(['api/apply', 'api/telemetry']);

async function forward(req: Request, path: string[], allowed: Set<string>) {
  const joined = path.join('/');
  if (!allowed.has(joined)) {
    return Response.json(
      { error: `${req.method} /api/backend/${joined} is not proxied.` },
      { status: 404 },
    );
  }

  const url = new URL(req.url);
  const res = await fetch(`${BACKEND}/${joined}${url.search}`, {
    method: req.method,
    headers: { 'Content-Type': 'application/json' },
    body: req.method === 'GET' || req.method === 'HEAD' ? undefined : await req.text(),
    cache: 'no-store',
  });
  return new Response(await res.text(), {
    status: res.status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function GET(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path, READABLE);
}

export async function POST(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path, WRITABLE);
}
