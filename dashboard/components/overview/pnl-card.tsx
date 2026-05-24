// dashboard/components/overview/pnl-card.tsx
"use client";
import useSWR from "swr";
import { api, type Portfolio } from "@/lib/api";

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

export function PnlCard() {
  const { data, isLoading } = useSWR<Portfolio>("portfolio", api.portfolio, { refreshInterval: 10000 });

  if (isLoading || !data) return <div className="h-32 bg-surface animate-pulse rounded-xl" />;

  const pnl = data.total_value - 100000;
  const pnlPct = (pnl / 100000) * 100;
  const isPos = pnl >= 0;

  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
      <p className="text-muted text-xs uppercase tracking-widest">Portfolio Value</p>
      <p className="text-3xl font-bold">{fmt(data.total_value)}</p>
      <p className={`text-sm font-medium ${isPos ? "text-accent" : "text-danger"}`}>
        {isPos ? "▲" : "▼"} {fmt(Math.abs(pnl))} ({pnlPct.toFixed(2)}%) all time
      </p>
      <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border text-center">
        <div>
          <p className="text-xs text-muted">Cash</p>
          <p className="font-medium text-sm">{fmt(data.cash)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Peak</p>
          <p className="font-medium text-sm">{fmt(data.peak_value)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Positions</p>
          <p className="font-medium text-sm">{data.open_positions}</p>
        </div>
      </div>
    </div>
  );
}
