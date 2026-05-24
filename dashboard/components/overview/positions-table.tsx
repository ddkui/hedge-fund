// dashboard/components/overview/positions-table.tsx
"use client";
import useSWR from "swr";
import { api, type Position } from "@/lib/api";

export function PositionsTable() {
  const { data = [], isLoading } = useSWR<Position[]>("positions", api.positions, { refreshInterval: 15000 });

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest">Open Positions</h2>
      {isLoading ? (
        <div className="h-20 animate-pulse bg-border rounded" />
      ) : data.length === 0 ? (
        <p className="text-muted text-sm">No open positions</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2">Symbol</th>
              <th className="text-left py-2">Direction</th>
              <th className="text-right py-2">Qty</th>
              <th className="text-right py-2">Entry</th>
              <th className="text-left py-2 pl-4">Thesis</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 font-mono font-medium">{p.symbol}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${p.direction === "long" ? "bg-accent/10 text-accent" : "bg-danger/10 text-danger"}`}>
                    {p.direction.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 text-right font-mono">{p.quantity.toFixed(4)}</td>
                <td className="py-2 text-right font-mono">${p.entry_price.toFixed(2)}</td>
                <td className="py-2 pl-4 text-muted text-xs truncate max-w-xs">{p.entry_thesis ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
