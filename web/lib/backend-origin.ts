// Where the Python service is, as something `fetch` can actually use.
//
// Its own module because two files need it and both had their own copy of the default, which
// is how two copies drift. Kept free of path aliases so either can import it relatively and
// still be unit-tested under plain node.

const LOCAL = 'http://127.0.0.1:8000';

/**
 * Normalise whatever `UNLOGGED_API` holds into an origin.
 *
 * Render's `fromService` can only hand over a bare `host` or `host:port` — a blueprint cannot
 * interpolate a scheme in front of one. `fetch('unlogged-api.onrender.com/api/engagement')`
 * throws `ERR_INVALID_URL`, and `fetch('unlogged-api:10000/…')` is worse: it parses, because
 * `unlogged-api:` reads as a scheme, and fails as a network error that looks like the service
 * being down. So the blueprint shipped a web half that could not reach its own API, and the
 * symptom would have been an empty dashboard rather than anything naming the cause.
 *
 * A value that already carries a scheme is left exactly as it is — compose's `http://api:8000`
 * has to keep its port and its plain http.
 */
export function backendOrigin(value: string | undefined | null): string {
  const raw = (value ?? '').trim();
  if (!raw) return LOCAL;
  const origin = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  // A trailing slash would make every path `//api/...`, which some servers route differently
  // and none route better.
  return origin.replace(/\/+$/, '');
}
