import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next writes AGENTS.md and CLAUDE.md into the project on every dev start. They are
  // generated scaffolding, not part of this codebase, and they land as untracked files in a
  // repository that is going to be read by people. Off.
  agentRules: false,
};

export default nextConfig;
