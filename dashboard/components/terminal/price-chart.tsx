// dashboard/components/terminal/price-chart.tsx
"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { api, type Trade } from "@/lib/api";

const WATCHLIST = ["AAPL", "MSFT", "NVDA", "BTCUSDT", "ETHUSDT", "SOLUSDT", "SPY"];

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
  volume: number;
}

export function PriceChart() {
  const chartRef = useRef<HTMLDivElement>(null);
  const volumeRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeries = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [selected, setSelected] = useState("BTCUSDT");
  const [period, setPeriod] = useState(PERIODS[1]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);

  // Build chart once
  useEffect(() => {
    if (!chartRef.current) return;

    const chart = createChart(chartRef.current, {
      layout: { background: { color: "#13131a" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#1e1e2e" },
      timeScale: { borderColor: "#1e1e2e", timeVisible: true, secondsVisible: false },
      width: chartRef.current.clientWidth,
      height: 340,
    });

    const candles = chart.addCandlestickSeries({
      upColor: "#00d4aa",
      downColor: "#ff4757",
      borderVisible: false,
      wickUpColor: "#00d4aa",
      wickDownColor: "#ff4757",
    });

    const vol = chart.addHistogramSeries({
      color: "#26a69a",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartInstance.current = chart;
    candleRef.current = candles;
    volumeSeries.current = vol;

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
    if (!candleRef.current || !volumeSeries.current) return;
    setLoading(true);
    setError(null);
    try {
      // Load candle data
      const res = await fetch(
        `/api/prices/${selected}?period=${period.value}&interval=${period.interval}`
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const candles: Candle[] = await res.json();

      if (candles.length === 0) {
        setError("No price data available");
        setLoading(false);
        return;
      }

      candleRef.current.setData(
        candles.map((c) => ({
          time: c.time as Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
      );

      volumeSeries.current.setData(
        candles.map((c) => ({
          time: c.time as Time,
          value: c.volume ?? 0,
          color: c.close >= c.open ? "#00d4aa33" : "#ff475733",
        }))
      );

      // Set last price and change
      const last = candles[candles.length - 1];
      const first = candles[0];
      setLastPrice(last.close);
      setPriceChange(((last.close - first.open) / first.open) * 100);

      // Add trade markers for this symbol
      try {
        const trades = await api.trades(200);
        const symbolTrades = trades.filter(
          (t: Trade) => t.symbol === selected && t.status === "executed" && t.price > 0
        );

        if (symbolTrades.length > 0) {
          // Convert trade times to chart time scale
          const candleTimes = new Set(candles.map((c) => c.time));
          const markers: SeriesMarker<Time>[] = symbolTrades
            .map((t: Trade) => {
              const tradeTime = Math.floor(new Date(t.time).getTime() / 1000);
              // Snap to nearest candle time
              const candleArr = candles.map((c) => c.time);
              const nearest = candleArr.reduce((prev, curr) =>
                Math.abs(curr - tradeTime) < Math.abs(prev - tradeTime) ? curr : prev
              );
              return {
                time: nearest as Time,
                position: t.action === "close" || t.action === "short" ? "aboveBar" : "belowBar",
                color: t.action === "close" || t.action === "short" ? "#ff4757" : "#00d4aa",
                shape: t.action === "close" ? "arrowDown" : "arrowUp",
                text: `${t.action.toUpperCase()} @${t.price.toFixed(2)}`,
              } satisfies SeriesMarker<Time>;
            });
          if (markers.length > 0) {
            // Sort by time (required by lightweight-charts)
            markers.sort((a, b) => (a.time as number) - (b.time as number));
            candleRef.current.setMarkers(markers);
          }
        }
      } catch {
        // trade markers are best-effort, don't fail the chart
      }

      chartInstance.current?.timeScale().fitContent();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load prices");
    } finally {
      setLoading(false);
    }
  }, [selected, period]);

  useEffect(() => {
    loadCandles();
    // Auto-refresh every 30s for live data
    const id = setInterval(loadCandles, 30000);
    return () => clearInterval(id);
  }, [loadCandles]);

  const changeColor = priceChange == null ? "text-muted" : priceChange >= 0 ? "text-accent" : "text-danger";

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">
            Market Chart
          </h2>
          {lastPrice != null && (
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-lg font-bold font-mono">
                ${lastPrice.toLocaleString("en-US", { maximumFractionDigits: 4 })}
              </span>
              {priceChange != null && (
                <span className={`text-sm ${changeColor}`}>
                  {priceChange >= 0 ? "▲" : "▼"} {Math.abs(priceChange).toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>

        {/* Symbol selector */}
        <div className="flex gap-1 flex-wrap ml-4">
          {WATCHLIST.map((sym) => (
            <button
              key={sym}
              onClick={() => setSelected(sym)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                selected === sym
                  ? "bg-accent text-black font-bold"
                  : "bg-border text-muted hover:text-white"
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
                period.value === p.value
                  ? "bg-accent/20 text-accent border border-accent/40"
                  : "bg-border text-muted hover:text-white"
              }`}
            >
              {p.label}
            </button>
          ))}
          <button
            onClick={loadCandles}
            className="px-2.5 py-1 rounded text-xs text-muted hover:text-white bg-border"
          >
            ↻
          </button>
        </div>

        {loading && <span className="text-xs text-muted animate-pulse ml-2">Loading…</span>}
        {error && <span className="text-xs text-danger ml-2">{error}</span>}
      </div>

      <div ref={chartRef} className="rounded overflow-hidden" />
      <p className="text-xs text-muted mt-2">
        ▲ = entry / ▼ = exit — trade markers from executed orders
      </p>
    </div>
  );
}
