'use client';

import { useEffect } from 'react';
import { AlertIcon } from './components/ui/icons';
import { AppShell } from './components/app-shell';
import { SidebarSkeleton } from './components/skeleton';
import { Button } from './components/ui/ui';

// The last resort, when rendering the page itself threw.
//
// It used to say the PayPal sandbox had not responded and to go and check API credentials in
// .env.local — three things wrong at once. This page never calls PayPal; it calls the Python
// service, which replays recorded exchanges by default. It needs no PayPal credentials to run
// at all, and .env.local holds the OpenAI key for the assistant, not a PayPal one. A reader
// who followed that would have gone looking for a credential that is not the problem and
// never would be.
//
// A service that is merely not running no longer reaches here: the page reads that case and
// says so in the header. What is left is a real fault, so the message is shown rather than
// summarised.
export default function DashboardError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <AppShell sidebar={<SidebarSkeleton />}>
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-lg rounded-lg border border-pp-border bg-white p-8 text-center">
          <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-pp-danger/10 text-pp-danger">
            <AlertIcon className="size-7" />
          </span>
          <h1 className="mt-4 text-2xl font-semibold text-pp-navy">The dashboard didn&apos;t load</h1>
          <p className="mt-2 text-[15px] text-pp-muted">
            This page reads from the Python service, not from PayPal, and needs no PayPal
            credentials. If the service is not running, start it with{' '}
            <code className="rounded bg-pp-canvas px-1">
              uv run uvicorn unlogged.web:app --port 8000
            </code>{' '}
            and try again. Otherwise what went wrong is below, in full.
          </p>
          {error.message && (
            <p className="mt-4 break-words rounded-lg bg-pp-canvas px-4 py-3 text-left font-mono text-xs text-pp-muted">
              {error.message}
              {error.digest && <span className="block pt-1">Reference: {error.digest}</span>}
            </p>
          )}
          <Button variant="primary" className="mt-6" onClick={retry}>
            Try again
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
