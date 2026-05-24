// dashboard/components/overview/regime-badge.tsx
"use client";
import useSWR from "swr";
import { api, type Signal } from "@/lib/api";

const REGIME_COLORS: Record<string, string> = {
  "expansion": "text-accent bg-accent/10",
  "contraction": "text-danger bg-danger/10",
  "stagflation": "text-warning bg-warning/10",
  "hiking_cycle": "text-orange-400 bg-orange-400/10",
  "cutting_cycle": "text-blue-400 bg-blue-400/10",
};

export function RegimeBadge() {
  const { data = [] } = useSWR<Signal[]>(
    "signals-macro",
    () => api.signalsForSymbol("MACRO"),
    { refreshInterval: 60000 }
  );

  const latest = data.find((s) => s.agent === "macro");
  const regime = latest?.signal_type ?? "unknown";
  const colorClass = REGIME_COLORS[regime] ?? "text-muted bg-muted/10";

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <p className="text-muted text-xs uppercase tracking-widest mb-2">Market Regime</p>
      <span className={`px-3 py-1.5 rounded-lg text-sm font-semibold uppercase tracking-wide ${colorClass}`}>
        {regime.replace(/_/g, " ")}
      </span>
      {latest && (
        <p className="text-xs text-muted mt-2">{latest.reasoning?.slice(0, 120)}…</p>
      )}
    </div>
  );
}
