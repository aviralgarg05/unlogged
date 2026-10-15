// Telemetry observer, piped to the backend so AgentUnit can score the runs.
//
// Three of eleven surveyed AG Studio entries register an observer. None publishes an
// evaluation from one. The observer contract runs `onEvent` synchronously in-loop, which is
// the useful part: reading `api.getState()` inside a tool-finished event sees the exact
// post-mutation state that call produced, not whatever the dashboard settles on later.
//
// It must stay cheap. A throwing observer is isolated and skipped, so a failure here is
// silent — the events are queued and flushed on a timer rather than awaited on the hot path.

import type { AgAiTelemetryEvent, AgAiTelemetryObserver, AgStudioApi } from 'ag-studio';

const FLUSH_MS = 2000;
const MAX_BUFFER = 200;

type Record_ = {
  at: string;
  type: string;
  agent?: string;
  tool?: string;
  usage?: unknown;
  pageId?: string | null;
};

export function unloggedTelemetry(api: AgStudioApi): AgAiTelemetryObserver {
  let buffer: Record_[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;

  const flush = () => {
    timer = null;
    if (buffer.length === 0) return;
    const batch = buffer;
    buffer = [];
    // Fire and forget: telemetry must never delay or fail a run.
    void fetch('/api/backend/api/telemetry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    }).catch(() => undefined);
  };

  return {
    onEvent(event: AgAiTelemetryEvent) {
      const e = event as unknown as Record<string, unknown>;
      let pageId: string | null = null;
      try {
        // Point-in-time: read it here, inside the loop, not on the flush timer.
        pageId = (api.getState() as { selectedPageId?: string }).selectedPageId ?? null;
      } catch {
        pageId = null;
      }
      buffer.push({
        at: new Date().toISOString(),
        type: String(e.type ?? 'unknown'),
        agent: typeof e.agentId === 'string' ? e.agentId : undefined,
        tool: typeof e.toolName === 'string' ? e.toolName : undefined,
        usage: e.usage,
        pageId,
      });
      if (buffer.length >= MAX_BUFFER) flush();
      else if (timer === null) timer = setTimeout(flush, FLUSH_MS);
    },
  };
}
