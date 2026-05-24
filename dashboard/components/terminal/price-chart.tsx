// dashboard/components/terminal/price-chart.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi } from "lightweight-charts";

const WATCHLIST = ["AAPL", "MSFT", "NVDA", "BTCUSDT", "ETHUSDT", "SPY"];

export function PriceChart() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [selected, setSelected] = useState("AAPL");

  useEffect(() => {
    if (!chartRef.current) return;
    const chart = createChart(chartRef.current, {
      layout: { background: { color: "#13131a" }, textColor: "#6b7280" },
      grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
      width: chartRef.current.clientWidth,
      height: 400,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#00d4aa",
      downColor: "#ff4757",
      borderVisible: false,
      wickUpColor: "#00d4aa",
      wickDownColor: "#ff4757",
    });
    chartInstance.current = chart;
    seriesRef.current = series;

    const resize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    // Seed with placeholder candles until prices flow from ingest layer
    const now = Math.floor(Date.now() / 1000);
    const candles = Array.from({ length: 60 }, (_, i) => {
      const open = 150 + Math.random() * 20;
      return {
        time: (now - (59 - i) * 3600) as number,
        open,
        high: open + Math.random() * 5,
        low: open - Math.random() * 5,
        close: open + (Math.random() - 0.5) * 8,
      };
    });
    seriesRef.current.setData(candles);
  }, [selected]);

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Market Chart</h2>
        <div className="flex gap-1 ml-auto">
          {WATCHLIST.map((sym) => (
            <button
              key={sym}
              onClick={() => setSelected(sym)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                selected === sym ? "bg-accent text-black font-bold" : "bg-border text-muted hover:text-white"
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>
      <div ref={chartRef} />
    </div>
  );
}
