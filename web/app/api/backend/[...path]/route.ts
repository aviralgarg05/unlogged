// Proxy to the Python service. Keeps the backend off the public internet in a deployment
// and gives the browser a same-origin endpoint.

import { BACKEND } from '@/lib/backend';

async function forward(req: Request, path: string[]) {
  const url = new URL(req.url);
  const target = `${BACKEND}/${path.join('/')}${url.search}`;
  const res = await fetch(target, {
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
  return forward(req, (await ctx.params).path);
}

export async function POST(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}
