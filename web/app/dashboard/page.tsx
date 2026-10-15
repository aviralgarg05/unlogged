import type { Metadata } from "next";
import { connection } from "next/server";
import { aiEnabled, aiModels } from "@/lib/ai";
import { Dashboard } from "./dashboard";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default async function DashboardPage() {
  // Rows are fetched per page by the Studio data source, not materialised here.
  await connection();

  // Only the model ids reach the client; the OpenAI key stays on the server (lib/ai.ts).
  return (
    <Dashboard
      licenseKey={process.env.AG_STUDIO}
      aiModels={aiEnabled() ? aiModels() : undefined}
    />
  );
}
