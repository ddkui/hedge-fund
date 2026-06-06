"use client";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";
import { useState } from "react";

interface KronosForecast {
  symbol: string;
  signal_type: string;
  pred_change_pct: number;
  pred_close: number;
  pred_high: number;
  pred_low: number;
  confidence: number;
  pred_horizon_candles: number;
  time: string;
  reasoning: string;
}

function SignalBadge({ signal }: { signal: string }) {
  const isBullish = signal.includes("bullish");
  const isBearish = signal.includes("bearish");
  const label = signal.replace("_signal", "").toUpperCase();
  const cls = isBullish
    ? "bg-accent/10 text-accent border border-accent/20"
    : isBearish
    ? "bg-danger/10 text-danger border border-danger/20"
    : "bg-muted/10 text-muted border border-muted/20";
  const arrow = isBullish ? "▲" : isBearish ? "▼" : "◆";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {arrow} {label}
    </span>
  );
}

function ChangeCell({ pct }: { pct: number }) {
  const isPos = pct >= 0;
  return (
    <span className={`font-mono font-bold ${isPos ? "text-accent" : "text-danger"}`}>
      {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
    </span>
  );
}

function ConfBar({ conf }: { conf: number }) {
  const w = Math.round(conf);
  const color = conf >= 60 ? "#00d4aa" : conf >= 40 ? "#ffa502" : "#6b7280";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-border rounded-full h-1.5">
        <div className="h-1.5 rounded-full transition-all" style={{ width: `${w}%`, background: color }} />
      </div>
      <span className="text-xs text-muted w-8 text-right">{w}%</span>
    </div>
  );
}

export default function KronosPage() {
  const { data: forecasts = [], isLoading } = useSWR<KronosForecast[]>(
    "kronos-forecasts",
    () => apiFetch("/kronos/forecasts"),
    { refreshInterval: 60000 },
  );
  const [downloading, setDownloading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const bullish = forecasts.filter((f) => f.signal_type.includes("bullish"));
  const bearish = forecasts.filter((f) => f.signal_type.includes("bearish"));
  const neutral = forecasts.filter((f) => f.signal_type.includes("neutral"));

  const sorted = [...forecasts].sort((a, b) => b.pred_change_pct - a.pred_change_pct);

  function downloadPdf() {
    setDownloading(true);
    const a = document.createElement("a");
    a.href = "/api/kronos/report.pdf";
    a.download = `kronos-report-${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => setDownloading(false), 2000);
  }

  const lastUpdated = forecasts[0]?.time
    ? new Date(forecasts[0].time).toLocaleString()
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Kronos Research</h1>
          <p className="text-sm text-muted mt-0.5">
            NeoQuasar/Kronos-mini · Foundation model price forecasts
            {lastUpdated && ` · Updated ${lastUpdated}`}
          </p>
        </div>
        <button
          onClick={downloadPdf}
          disabled={downloading || forecasts.length === 0}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-black text-sm font-bold rounded-lg hover:bg-accent/80 disabled:opacity-40 transition-colors"
        >
          <span>{downloading ? "Generating…" : "⬇ Download PDF Report"}</span>
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Symbols", value: forecasts.length, color: "text-white" },
          { label: "Bullish", value: bullish.length, color: "text-accent" },
          { label: "Bearish", value: bearish.length, color: "text-danger" },
          { label: "Neutral", value: neutral.length, color: "text-muted" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-surface border border-border rounded-xl p-4 text-center">
            <p className="text-xs text-muted uppercase tracking-widest mb-1">{label}</p>
            <p className={`text-3xl font-bold ${color}`}>{isLoading ? "—" : value}</p>
          </div>
        ))}
      </div>

      {/* Forecast table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">
            Forecast Detail — {forecasts[0]?.pred_horizon_candles ?? 24} candle horizon
          </h2>
        </div>

        {isLoading ? (
          <div className="h-40 animate-pulse bg-border m-4 rounded" />
        ) : forecasts.length === 0 ? (
          <div className="p-8 text-center text-muted text-sm">
            No forecasts yet — run the Kronos agent first.<br />
            <code className="text-xs mt-2 block">python scripts/run_kronos_once.py</code>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted text-xs border-b border-border">
                <th className="text-left px-5 py-3">Symbol</th>
                <th className="text-left px-3 py-3">Signal</th>
                <th className="text-right px-3 py-3">Change</th>
                <th className="text-right px-3 py-3">Predicted</th>
                <th className="text-right px-3 py-3">Low</th>
                <th className="text-right px-3 py-3">High</th>
                <th className="px-5 py-3 w-32">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((fc) => (
                <>
                  <tr
                    key={fc.symbol}
                    onClick={() => setExpanded(expanded === fc.symbol ? null : fc.symbol)}
                    className="border-b border-border/40 hover:bg-white/5 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3 font-mono font-bold">{fc.symbol}</td>
                    <td className="px-3 py-3">
                      <SignalBadge signal={fc.signal_type} />
                    </td>
                    <td className="px-3 py-3 text-right">
                      <ChangeCell pct={fc.pred_change_pct} />
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-slate-300">
                      {fc.pred_close.toFixed(4)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-danger/80">
                      {fc.pred_low.toFixed(4)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-accent/80">
                      {fc.pred_high.toFixed(4)}
                    </td>
                    <td className="px-5 py-3">
                      <ConfBar conf={fc.confidence} />
                    </td>
                  </tr>
                  {expanded === fc.symbol && (
                    <tr key={`${fc.symbol}-detail`} className="border-b border-border/40 bg-border/20">
                      <td colSpan={7} className="px-5 py-3 text-xs text-muted leading-relaxed">
                        {fc.reasoning}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* PDF preview hint */}
      {forecasts.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">PDF Research Report</p>
            <p className="text-xs text-muted mt-0.5">
              Full formatted report with forecast table and disclaimer — ready to download or share
            </p>
          </div>
          <button
            onClick={downloadPdf}
            disabled={downloading}
            className="px-4 py-2 border border-accent text-accent text-sm rounded-lg hover:bg-accent hover:text-black transition-colors disabled:opacity-40"
          >
            {downloading ? "Generating…" : "Open PDF"}
          </button>
        </div>
      )}
    </div>
  );
}
