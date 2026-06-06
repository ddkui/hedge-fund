// dashboard/components/analytics/drawdown-chart.tsx
"use client";
import { Chart, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler } from "chart.js";
import { Line } from "react-chartjs-2";

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler);

interface DrawdownChartProps {
  labels: string[];
  drawdown: number[];
}

export function DrawdownChart({ labels, drawdown }: DrawdownChartProps) {
  const data = {
    labels: labels.map((l) => new Date(l).toLocaleDateString()),
    datasets: [
      {
        label: "Drawdown %",
        data: drawdown,
        borderColor: "#ff4757",
        backgroundColor: "rgba(255,71,87,0.15)",
        fill: true,
        tension: 0.3,
        pointRadius: 1,
        borderWidth: 1.5,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "#1e1e2e" } },
      y: { ticks: { color: "#6b7280", callback: (v: unknown) => `${v}%` }, grid: { color: "#1e1e2e" }, max: 0 },
    },
  };
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Drawdown</h2>
      <div style={{ height: 240 }}>
        <Line data={data} options={options} />
      </div>
    </div>
  );
}
