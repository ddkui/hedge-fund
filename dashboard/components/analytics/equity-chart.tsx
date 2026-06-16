// dashboard/components/analytics/equity-chart.tsx
"use client";
import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";

interface EquityChartProps {
  labels: string[];
  values: number[];
}

export function EquityChart({ labels, values }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { color: "#13131a" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
      rightPriceScale: { borderColor: "#1e1e2e" },
      timeScale: { borderColor: "#1e1e2e" },
      width: containerRef.current.clientWidth,
      height: 240,
    });
    const series = chart.addAreaSeries({
      lineColor: "#00d4aa",
      topColor: "rgba(0,212,170,0.25)",
      bottomColor: "rgba(0,212,170,0.02)",
      lineWidth: 2,
      priceFormat: {
        type: "custom",
        formatter: (p: number) => `$${p.toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
        minMove: 1,
      },
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const resize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !labels.length) return;
    const data = labels
      .map((l, i) => ({ time: l.slice(0, 10) as Time, value: values[i] ?? 0 }))
      .filter((d, i, arr) => i === 0 || d.time !== arr[i - 1].time);
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [labels, values]);

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">Equity Curve</h2>
      <div ref={containerRef} />
    </div>
  );
}
