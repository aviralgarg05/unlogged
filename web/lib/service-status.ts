// Whether the Python service answered, in the words the header puts on the page.
//
// The status line was a green dot and "PayPal sandbox", drawn unconditionally. Start the
// dashboard without the API — which is what `docker compose up` does for the few seconds
// before the API is listening, and what anyone running only `npm start` does — and the page
// reported a healthy sandbox connection above three empty grids. A light that is green
// whatever happened is worse than no light, because a reader believes it.

export type ServiceStatus = { reachable: boolean; currency?: string };

export type StatusLine = {
  /** The dot's tone. `ok` is the only one that should read as healthy. */
  tone: 'ok' | 'down';
  label: string;
  /** What a reader can do about it, or null when there is nothing to do. */
  hint: string | null;
};

export function statusLine(status: ServiceStatus): StatusLine {
  if (status.reachable) {
    return { tone: 'ok', label: 'PayPal sandbox', hint: null };
  }
  return {
    tone: 'down',
    label: 'Service not reachable',
    hint: 'Start it with `uv run uvicorn unlogged.web:app --port 8000`, then refresh.',
  };
}
