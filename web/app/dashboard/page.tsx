import type { Metadata } from "next";
import { connection } from "next/server";
import { aiEnabled, aiModels } from "@/lib/ai";
import { fetchEngagement } from "@/lib/backend";
import type { ServiceStatus } from "@/lib/service-status";
import { Dashboard } from "./dashboard";

export const metadata: Metadata = {
  title: "Dashboard",
};

/**
 * One call to the Python service: whether it answered, and the currency to format money in.
 *
 * Read here rather than in the browser because the fields are declared when Studio is built,
 * and a second render to add a currency symbol would reset the open report. The rows
 * themselves are still fetched a page at a time by the data source.
 *
 * If the service is unreachable the page still renders, because it recovers on its own as
 * soon as the service is up and the header carries a refresh. What it does not do is draw a
 * green light over three empty grids: the figures stay unsymbolled rather than carrying a
 * currency nobody confirmed, and the header says what is wrong and how to fix it.
 */
async function serviceStatus(): Promise<ServiceStatus> {
  try {
    return { reachable: true, currency: (await fetchEngagement()).currency };
  } catch {
    return { reachable: false };
  }
}

export default async function DashboardPage() {
  // Rows are fetched per page by the Studio data source, not materialised here.
  await connection();

  // Only the model ids reach the client; the OpenAI key stays on the server (lib/ai.ts).
  return (
    <Dashboard
      licenseKey={process.env.AG_STUDIO}
      aiModels={aiEnabled() ? aiModels() : undefined}
      service={await serviceStatus()}
    />
  );
}
