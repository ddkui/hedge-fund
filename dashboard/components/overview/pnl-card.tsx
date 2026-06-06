// dashboard/components/overview/pnl-card.tsx
"use client";
import useSWR from "swr";
import { api, type Portfolio } from "@/lib/api";

const INITIAL_CAPITAL = 100_000;

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function fmtPrecise(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(n);
}

export function PnlCard() {
  const { data, isLoading } = useSWR<Portfolio>("portfolio", api.portfolio, {
    refreshInterval: 6000,
    revalidateOnFocus: true,
  });

  if (isLoading || !data) return <div className="h-36 bg-surface animate-pulse rounded-xl" />;

  const pnl = data.total_value - INITIAL_CAPITAL;
  const pnlPct = (pnl / INITIAL_CAPITAL) * 100;
  const isPos = pnl >= 0;
  const drawdown = data.peak_value > 0 ? ((data.peak_value - data.total_value) / data.peak_value) * 100 : 0;

  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-muted text-xs uppercase tracking-widest">Portfolio Value</p>
        <span className="text-xs text-muted">Mark-to-Market</span>
      </div>
      <p className="text-3xl font-bold font-mono">{fmt(data.total_value)}</p>
      <p className={`text-sm font-medium ${isPos ? "text-accent" : "text-danger"}`}>
        {isPos ? "▲" : "▼"} {fmtPrecise(Math.abs(pnl))} ({pnlPct.toFixed(2)}%) vs start
      </p>
      <div className="grid grid-cols-4 gap-2 pt-2 border-t border-border text-center">
        <div>
          <p className="text-xs text-muted">Cash</p>
          <p className="font-medium text-sm font-mono">{fmt(data.cash)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Positions</p>
          <p className="font-medium text-sm font-mono">{fmt(data.total_value - data.cash)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Peak</p>
          <p className="font-medium text-sm font-mono">{fmt(data.peak_value)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Drawdown</p>
          <p className={`font-medium text-sm ${drawdown > 5 ? "text-danger" : "text-muted"}`}>
            {drawdown.toFixed(2)}%
          </p>
        </div>
      </div>
    </div>
  );
}
