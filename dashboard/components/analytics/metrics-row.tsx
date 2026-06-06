// dashboard/components/analytics/metrics-row.tsx
"use client";

interface Metrics {
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  win_rate: number;
  cagr: number;
  total_pnl: number;
  trade_count: number;
  error?: string;
}

interface MetricsRowProps {
  data: Metrics | null;
  isLoading: boolean;
}

function StatCard({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 text-center">
      <p className="text-xs text-muted uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-2xl font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}

export function MetricsRow({ data, isLoading }: MetricsRowProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-surface border border-border rounded-xl p-4 h-20 animate-pulse" />
        ))}
      </div>
    );
  }
  if (!data || data.error) {
    return (
      <div className="bg-surface border border-border rounded-xl p-4 text-center text-muted text-sm">
        Not enough trading history yet — make some trades first.
      </div>
    );
  }
  const pnlColor = data.total_pnl >= 0 ? "text-accent" : "text-danger";
  return (
    <div className="grid grid-cols-6 gap-3">
      <StatCard label="Sharpe" value={data.sharpe.toFixed(2)} color={data.sharpe >= 1 ? "text-accent" : "text-warning"} />
      <StatCard label="Sortino" value={data.sortino.toFixed(2)} color={data.sortino >= 1 ? "text-accent" : "text-warning"} />
      <StatCard label="Max Drawdown" value={`-${data.max_drawdown.toFixed(2)}%`} color="text-danger" />
      <StatCard label="Win Rate" value={`${(data.win_rate * 100).toFixed(1)}%`} color={data.win_rate >= 0.5 ? "text-accent" : "text-danger"} />
      <StatCard label="CAGR" value={`${data.cagr.toFixed(2)}%`} color={data.cagr >= 0 ? "text-accent" : "text-danger"} />
      <StatCard label="Total P&L" value={`$${data.total_pnl.toLocaleString("en-US", { maximumFractionDigits: 0 })}`} color={pnlColor} />
    </div>
  );
}
