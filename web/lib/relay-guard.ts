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
const seen = new Map<string, number[]>();

/**
 * A coarse per-caller cap. In-process and therefore per-instance, which is honest about what
 * it is: a brake, not a quota. It bounds a single stranger, not a determined one.
 */
export function withinRate(request: Request): boolean {
  const who =
    request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
    request.headers.get('x-real-ip') ||
    'unknown';
  const now = Date.now();
  const hits = (seen.get(who) ?? []).filter((t) => now - t < WINDOW_MS);
  hits.push(now);
  seen.set(who, hits);

  if (seen.size > 1_000) {
    // Never let the brake itself become the leak.
    for (const [key, times] of seen) {
      if (times.every((t) => now - t >= WINDOW_MS)) seen.delete(key);
    }
  }
  return hits.length <= MAX_PER_WINDOW;
}
