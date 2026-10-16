// Bounds on the two routes that spend the owner's OpenAI credit.
//
// Neither route takes a credential, because the caller is a browser running the dashboard. On
// a deployed demo that makes them an open relay: anyone who finds the URL can spend the key
// behind them, and the bill arrives quietly.
//
// What is here is not authentication and is not described as such. It is two cheap bounds that
// turn "unlimited by anyone" into "a nuisance at worst", which is the right trade for a demo
// whose whole value is being runnable. Real deployment wants a session behind it.

/** Requests a browser makes from another site, or with a forged-looking origin, are refused. */
export function sameOrigin(request: Request): boolean {
  // Set by browsers on every cross-origin fetch and absent on same-origin navigations in some
  // engines, so its absence is not treated as hostile — only a stated foreign origin is.
  const site = request.headers.get('sec-fetch-site');
  if (site && site !== 'same-origin' && site !== 'none') return false;

  const origin = request.headers.get('origin');
  if (!origin) return true;
  try {
    return new URL(origin).host === new URL(request.url).host;
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
