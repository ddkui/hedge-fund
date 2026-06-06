// dashboard/app/analytics/page.tsx
"use client";
import useSWR from "swr";
import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { MetricsRow } from "@/components/analytics/metrics-row";
import { EquityChart } from "@/components/analytics/equity-chart";
import { ReturnsChart } from "@/components/analytics/returns-chart";
import { DrawdownChart } from "@/components/analytics/drawdown-chart";
import { PnlBySymbol } from "@/components/analytics/pnl-by-symbol";
import { MonthlyHeatmap } from "@/components/analytics/monthly-heatmap";
import { useWebSocket } from "@/lib/use-ws";

const RANGES = ["1d", "7d", "1m", "3m", "all"] as const;
type Range = typeof RANGES[number];

export default function AnalyticsPage() {
  const [range, setRange] = useState<Range>("7d");
  const { messages } = useWebSocket();

  const { data: summary, isLoading: sumLoading, mutate: mutateSummary } =
    useSWR(`analytics-summary-${range}`, () => apiFetch(`/analytics/summary?range=${range}`), { refreshInterval: 60000 });

  const { data: curve, isLoading: curveLoading, mutate: mutateCurve } =
    useSWR(`analytics-curve-${range}`, () => apiFetch(`/analytics/equity-curve?range=${range}`), { refreshInterval: 60000 });

  const { data: pnlData = [], isLoading: pnlLoading, mutate: mutatePnl } =
    useSWR(`analytics-pnl-${range}`, () => apiFetch(`/analytics/pnl-by-symbol?range=${range}`), { refreshInterval: 60000 });

  const { data: monthly = [], isLoading: monthlyLoading, mutate: mutateMonthly } =
    useSWR("analytics-monthly", () => apiFetch("/analytics/monthly-returns"), { refreshInterval: 300000 });

  // Refresh all charts when a trade executes
  useEffect(() => {
    const latest = messages[0];
    if (latest?.channel === "trade.executed") {
      mutateSummary();
      mutateCurve();
      mutatePnl();
      mutateMonthly();
    }
  }, [messages]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Performance Analytics</h1>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                range === r ? "bg-accent text-black" : "bg-border text-muted hover:text-white"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Key Metrics */}
      <MetricsRow data={summary as any} isLoading={sumLoading} />

      {/* Equity Curve + Daily Returns */}
      {curve && !(curve as any).error && (
        <div className="grid grid-cols-2 gap-4">
          <EquityChart labels={(curve as any).labels} values={(curve as any).equity} />
          <ReturnsChart labels={(curve as any).labels} returns={(curve as any).daily_returns} />
        </div>
      )}

      {/* Drawdown + P&L by Symbol */}
      <div className="grid grid-cols-2 gap-4">
        {curve && !(curve as any).error && (
          <DrawdownChart labels={(curve as any).labels} drawdown={(curve as any).drawdown} />
        )}
        {!pnlLoading && (pnlData as any[]).length > 0 && (
          <PnlBySymbol data={pnlData as any[]} />
        )}
      </div>

      {/* Monthly Heatmap */}
      {!monthlyLoading && (monthly as any[]).length > 0 && (
        <MonthlyHeatmap data={monthly as any[]} />
      )}
    </div>
  );
}
