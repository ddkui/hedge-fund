// dashboard/components/analytics/returns-chart.tsx
"use client";
import { Chart, BarElement, LinearScale, CategoryScale, Tooltip } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(BarElement, LinearScale, CategoryScale, Tooltip);

interface ReturnsChartProps {
  labels: string[];
  returns: number[];
}

export function ReturnsChart({ labels, returns }: ReturnsChartProps) {
  const data = {
    labels: labels.map((l) => new Date(l).toLocaleDateString()),
    datasets: [
      {
        label: "Daily Return %",
        data: returns,
        backgroundColor: returns.map((r) => (r >= 0 ? "rgba(0,212,170,0.7)" : "rgba(255,71,87,0.7)")),
        borderRadius: 2,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#6b7280", callback: (v: unknown) => `${v}%` }, grid: { color: "#1e1e2e" } },
    },
  };
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Daily Returns</h2>
      <div style={{ height: 240 }}>
        <Bar data={data} options={options} />
      </div>
    </div>
  );
}
