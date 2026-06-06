// dashboard/components/analytics/equity-chart.tsx
"use client";
import {
  Chart, LineElement, PointElement, LinearScale,
  CategoryScale, Tooltip, Legend, Filler, type ChartData,
} from "chart.js";
import { Line } from "react-chartjs-2";

Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler);

interface EquityChartProps {
  labels: string[];
  values: number[];
}

export function EquityChart({ labels, values }: EquityChartProps) {
  const data: ChartData<"line"> = {
    labels: labels.map((l) => new Date(l).toLocaleDateString()),
    datasets: [
      {
        label: "Portfolio Value",
        data: values,
        borderColor: "#00d4aa",
        backgroundColor: "rgba(0,212,170,0.08)",
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        borderWidth: 2,
      },
    ],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: "index" as const } },
    scales: {
      x: { ticks: { color: "#6b7280", maxTicksLimit: 8 }, grid: { color: "#1e1e2e" } },
      y: {
        ticks: { color: "#6b7280", callback: (v: unknown) => `$${Number(v).toLocaleString()}` },
        grid: { color: "#1e1e2e" },
      },
    },
  };
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Equity Curve</h2>
      <div style={{ height: 240 }}>
        <Line data={data} options={options} />
      </div>
    </div>
  );
}
