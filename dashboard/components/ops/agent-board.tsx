// dashboard/components/ops/agent-board.tsx
"use client";
import useSWR from "swr";
import { api, type AgentHealth } from "@/lib/api";

const STATUS_CONFIG = {
  healthy:  { color: "text-accent",   dot: "bg-accent",   label: "HEALTHY" },
  degraded: { color: "text-warning",  dot: "bg-warning",  label: "DEGRADED" },
  down:     { color: "text-danger",   dot: "bg-danger",   label: "DOWN" },
};

const ALL_AGENTS = [
  "ingest", "technical", "sentiment", "macro", "research", "aggregator",
  "momentum", "mean_reversion", "ml_quant", "quant_supervisor",
  "portfolio_mgr", "risk", "execution", "cio", "ops",
];

export function AgentBoard() {
  const { data = [], isLoading } = useSWR<AgentHealth[]>(
    "agent-health",
    api.agentHealth,
    { refreshInterval: 10000 }
  );

  const byAgent = Object.fromEntries(data.map((h) => [h.agent, h]));

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-4 text-muted uppercase tracking-widest">Agent Status Board</h2>
      {isLoading ? (
        <div className="h-40 animate-pulse bg-border rounded" />
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {ALL_AGENTS.map((agent) => {
            const health = byAgent[agent];
            const status = (health?.status ?? "down") as keyof typeof STATUS_CONFIG;
            const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.down;
            return (
              <div key={agent} className="border border-border rounded-lg p-3 flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
                <div>
                  <p className="text-sm font-medium capitalize">{agent.replace(/_/g, " ")}</p>
                  <p className={`text-xs ${cfg.color}`}>{cfg.label}</p>
                  {health && (
                    <p className="text-xs text-muted">{new Date(health.time).toLocaleTimeString()}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
