// dashboard/components/terminal/price-chart.tsx
"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { createChart } from "lightweight-charts";
import type { IChartApi, ISeriesApi } from "lightweight-charts";

const WATCHLIST = ["AAPL", "MSFT", "NVDA", "BTCUSDT", "ETHUSDT", "SPY"];

const PERIODS = [
  { label: "1D", value: "1d", interval: "5m" },
  { label: "5D", value: "5d", interval: "1h" },
  { label: "1M", value: "1mo", interval: "1d" },
  { label: "3M", value: "3mo", interval: "1d" },
];

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export function PriceChart() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [selected, setSelected] = useState("AAPL");
  const [period, setPeriod] = useState(PERIODS[1]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Build chart once
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

  // Fetch candles when symbol or period changes
  const loadCandles = useCallback(async () => {
    if (!seriesRef.current) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/prices/${selected}?period=${period.value}&interval=${period.interval}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const candles: Candle[] = await res.json();
      seriesRef.current.setData(candles);
      chartInstance.current?.timeScale().fitContent();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load prices");
    } finally {
      setLoading(false);
    }
  }, [selected, period]);

  useEffect(() => { loadCandles(); }, [loadCandles]);

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Market Chart</h2>

        {/* Symbol selector */}
        <div className="flex gap-1">
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

        {/* Period selector */}
        <div className="flex gap-1 ml-auto">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
                period.value === p.value ? "bg-accent/20 text-accent border border-accent/40" : "bg-border text-muted hover:text-white"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Status */}
        {loading && <span className="text-xs text-muted animate-pulse">Loading…</span>}
        {error && (
          <span className="text-xs text-danger">{error}</span>
        )}
      </div>

      <div ref={chartRef} />
    </div>
  );
}
