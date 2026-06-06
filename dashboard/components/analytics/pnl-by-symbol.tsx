// dashboard/components/analytics/pnl-by-symbol.tsx
"use client";
import { Chart, BarElement, LinearScale, CategoryScale, Tooltip } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(BarElement, LinearScale, CategoryScale, Tooltip);

interface PnlEntry { symbol: string; pnl: number; }

export function PnlBySymbol({ data }: { data: PnlEntry[] }) {
  const chartData = {
    labels: data.map((d) => d.symbol),
    datasets: [
      {
        label: "P&L ($)",
        data: data.map((d) => d.pnl),
        backgroundColor: data.map((d) => (d.pnl >= 0 ? "rgba(0,212,170,0.7)" : "rgba(255,71,87,0.7)")),
        borderRadius: 3,
      },
    ],
  };
  const options = {
    indexAxis: "y" as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", callback: (v: unknown) => `$${v}` }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#e2e8f0" }, grid: { color: "#1e1e2e" } },
    },
  };
  const height = Math.max(200, data.length * 36);
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">P&L by Symbol</h2>
      <div style={{ height }}>
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}
