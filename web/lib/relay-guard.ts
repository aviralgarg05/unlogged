// Bounds on the two routes that spend the owner's OpenAI credit.
//
// Neither route takes a credential, because the caller is a browser running the dashboard. On
// a deployed demo that makes them an open relay: anyone who finds the URL can spend the key
// behind them, and the bill arrives quietly.
//
// What is here is not authentication and is not described as such. It is two cheap bounds that
// turn "unlimited by anyone" into "a nuisance at worst", which is the right trade for a demo
// whose whole value is being runnable. Real deployment wants a session behind it.

/**
 * The host the browser addressed — which is not the one the server answers on.
 *
 * This compared `Origin` against `new URL(request.url).host`, and inside a container that host
 * is the server's own: Next listens on 0.0.0.0 and reconstructs the URL from the listen
 * address, so a browser at localhost:3000 sent `Origin: http://localhost:3000` and was
 * compared against `382b629e4d40:3000`. Every same-origin POST under the README's own
 * `docker compose up` was refused 403 — including the one button that moves money, and both
 * AI routes. The request's own `Host` header is what the browser addressed, so that is what
 * the origin has to match.
 *
 * `x-forwarded-host` first, for a deploy behind a proxy. A caller outside a browser can set
 * either header, but one outside a browser can also simply omit `Origin` and pass the check
 * below — this was never authentication and the file says so at the top.
 */
function addressedHost(request: Request): string | null {
  const stated = request.headers.get('x-forwarded-host') ?? request.headers.get('host');
  if (stated) return stated.split(',')[0].trim().toLowerCase() || null;
  try {
    return new URL(request.url).host.toLowerCase();
  } catch {
    return null;
  }
}

/** Requests a browser makes from another site, or with a forged-looking origin, are refused. */
export function sameOrigin(request: Request): boolean {
  // Set by browsers on every cross-origin fetch and absent on same-origin navigations in some
  // engines, so its absence is not treated as hostile — only a stated foreign origin is.
  const site = request.headers.get('sec-fetch-site');
  if (site && site !== 'same-origin' && site !== 'none') return false;

  const origin = request.headers.get('origin');
  if (!origin) return true;
  const addressed = addressedHost(request);
  if (!addressed) return false;
  try {
    return new URL(origin).host.toLowerCase() === addressed;
  } catch {
    return false;
  }
}

const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 30;
const MAX_GLOBAL_PER_WINDOW = 120;
const seen = new Map<string, number[]>();
let global: number[] = [];

/**
 * Two caps, because one is not enough and saying why matters more than the number.
 *
 * The per-caller key comes from `x-forwarded-for`, which the caller sends. Behind a proxy
 * that overwrites it this identifies someone; without one it identifies nothing, and a
 * stranger who varies the header walks past the per-caller cap entirely. So there is also a
 * global cap, which nobody can vary their way around — it is blunt, it would inconvenience a
 * real second user during an attack, and that is the correct trade for a route that spends
 * somebody's money and has no session behind it.
 *
 * A refused request does NOT extend either window. Counting refusals meant a caller already
 * over the limit kept the array growing and the filter re-scanning it, so the brake was its
 * own CPU and memory sink: refusing got more expensive the harder it was pushed.
 */
export function withinRate(request: Request): boolean {
  const who =
    request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
    request.headers.get('x-real-ip') ||
    'unknown';
  const now = Date.now();

  global = global.filter((t) => now - t < WINDOW_MS);
  const hits = (seen.get(who) ?? []).filter((t) => now - t < WINDOW_MS);

  if (hits.length >= MAX_PER_WINDOW || global.length >= MAX_GLOBAL_PER_WINDOW) {
    seen.set(who, hits);
    return false;
  }

  hits.push(now);
  seen.set(who, hits);
  global.push(now);

  if (seen.size > 1_000) {
    for (const [key, times] of seen) {
      if (times.every((t) => now - t >= WINDOW_MS)) seen.delete(key);
    }
  }
  return true;
}

/** Test seam: the caps are per-instance state and a suite needs to start from zero. */
export function resetRate(): void {
  seen.clear();
  global = [];
}
