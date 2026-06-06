// dashboard/components/overview/positions-table.tsx
"use client";
import useSWR from "swr";
import { api, type Position } from "@/lib/api";

function fmtPrice(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 }).format(n);
}
function fmtPnl(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(n);
}

export function PositionsTable() {
  const { data = [], isLoading } = useSWR<Position[]>("positions", api.positions, {
    refreshInterval: 8000,
    revalidateOnFocus: true,
  });

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest">
        Open Positions
      </h2>
      {isLoading ? (
        <div className="h-20 animate-pulse bg-border rounded" />
      ) : data.length === 0 ? (
        <p className="text-muted text-sm">No open positions</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted text-xs border-b border-border">
                <th className="text-left py-2">Symbol</th>
                <th className="text-left py-2">Side</th>
                <th className="text-right py-2">Qty</th>
                <th className="text-right py-2">Entry</th>
                <th className="text-right py-2">Current</th>
                <th className="text-right py-2">Unr. P&amp;L</th>
                <th className="text-right py-2">%</th>
                <th className="text-left py-2 pl-4">Thesis</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => {
                const pnlPositive = (p.unrealized_pnl ?? 0) >= 0;
                return (
                  <tr key={p.id} className="border-b border-border/50 hover:bg-white/5">
                    <td className="py-2 font-mono font-medium">{p.symbol}</td>
                    <td className="py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          p.direction === "long"
                            ? "bg-accent/10 text-accent"
                            : "bg-danger/10 text-danger"
                        }`}
                      >
                        {p.direction.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2 text-right font-mono">{p.quantity.toFixed(4)}</td>
                    <td className="py-2 text-right font-mono">{fmtPrice(p.entry_price)}</td>
                    <td className="py-2 text-right font-mono text-slate-300">
                      {p.current_price != null ? fmtPrice(p.current_price) : "—"}
                    </td>
                    <td
                      className={`py-2 text-right font-mono font-medium ${
                        pnlPositive ? "text-accent" : "text-danger"
                      }`}
                    >
                      {p.unrealized_pnl != null
                        ? `${pnlPositive ? "+" : ""}${fmtPnl(p.unrealized_pnl)}`
                        : "—"}
                    </td>
                    <td
                      className={`py-2 text-right text-xs ${
                        pnlPositive ? "text-accent" : "text-danger"
                      }`}
                    >
                      {p.unrealized_pnl_pct != null
                        ? `${pnlPositive ? "+" : ""}${p.unrealized_pnl_pct.toFixed(2)}%`
                        : "—"}
                    </td>
                    <td className="py-2 pl-4 text-muted text-xs truncate max-w-xs">
                      {p.entry_thesis ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
