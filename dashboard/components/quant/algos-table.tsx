// dashboard/components/quant/algos-table.tsx
"use client";
import useSWR from "swr";
import { api, type Algo } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  live:     "text-accent bg-accent/10",
  testing:  "text-warning bg-warning/10",
  approved: "text-blue-400 bg-blue-400/10",
  retired:  "text-muted bg-muted/10",
};

export function AlgosTable() {
  const { data: algos = [], isLoading } = useSWR<Algo[]>("algos", api.algos, { refreshInterval: 30000 });

  return (
    <div className="bg-surface border border-border rounded-xl p-5 overflow-auto">
      <h2 className="text-sm font-semibold mb-4 text-muted uppercase tracking-widest">Quant Algorithms</h2>
      {isLoading ? (
        <div className="h-40 animate-pulse bg-border rounded" />
      ) : algos.length === 0 ? (
        <p className="text-muted text-sm">No algos yet — agents will submit after first run</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2">Name</th>
              <th className="text-left py-2">Agent</th>
              <th className="text-left py-2">Type</th>
              <th className="text-center py-2">Status</th>
              <th className="text-right py-2">Sharpe</th>
              <th className="text-right py-2">Max DD</th>
              <th className="text-right py-2">Win %</th>
              <th className="text-right py-2">Trades</th>
            </tr>
          </thead>
          <tbody>
            {algos.map((a) => (
              <tr key={a.id} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 font-medium">{a.name}</td>
                <td className="py-2 text-muted text-xs">{a.quant_agent}</td>
                <td className="py-2 text-muted text-xs">{a.strategy_type}</td>
                <td className="py-2 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[a.status] ?? "text-muted"}`}>
                    {a.status.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 text-right font-mono">{a.sharpe_ratio?.toFixed(2) ?? "—"}</td>
                <td className="py-2 text-right font-mono text-danger">{a.max_drawdown ? `${(a.max_drawdown * 100).toFixed(1)}%` : "—"}</td>
                <td className="py-2 text-right font-mono">{a.win_rate ? `${(a.win_rate * 100).toFixed(1)}%` : "—"}</td>
                <td className="py-2 text-right font-mono">{a.trade_count ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
