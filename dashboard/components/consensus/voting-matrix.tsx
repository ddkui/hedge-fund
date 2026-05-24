// dashboard/components/consensus/voting-matrix.tsx
"use client";
import useSWR from "swr";
import { api, type Signal } from "@/lib/api";

const AGENTS = ["technical", "sentiment", "macro", "research", "aggregator"];

function directionColor(s: string) {
  if (s.includes("bullish")) return "bg-accent/20 text-accent";
  if (s.includes("bearish")) return "bg-danger/20 text-danger";
  return "bg-muted/20 text-muted";
}

export function VotingMatrix() {
  const { data: signals = [], isLoading } = useSWR<Signal[]>(
    "signals-all",
    () => api.signals(200),
    { refreshInterval: 20000 }
  );

  const matrix: Record<string, Record<string, Signal>> = {};
  for (const sig of signals) {
    if (!sig.symbol) continue;
    if (!matrix[sig.symbol]) matrix[sig.symbol] = {};
    if (!matrix[sig.symbol][sig.agent]) matrix[sig.symbol][sig.agent] = sig;
  }

  const symbols = Object.keys(matrix);

  return (
    <div className="bg-surface border border-border rounded-xl p-5 overflow-auto">
      <h2 className="text-sm font-semibold mb-4 text-muted uppercase tracking-widest">AI Consensus Matrix</h2>
      {isLoading ? (
        <div className="h-40 animate-pulse bg-border rounded" />
      ) : symbols.length === 0 ? (
        <p className="text-muted text-sm">No signals yet — waiting for agents</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2 pr-4">Symbol</th>
              {AGENTS.map((a) => (
                <th key={a} className="text-center py-2 px-3 capitalize">{a}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((sym) => (
              <tr key={sym} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 pr-4 font-mono font-bold">{sym}</td>
                {AGENTS.map((agent) => {
                  const sig = matrix[sym]?.[agent];
                  return (
                    <td key={agent} className="py-2 px-3 text-center">
                      {sig ? (
                        <span
                          title={sig.reasoning ?? ""}
                          className={`px-2 py-0.5 rounded text-xs cursor-help ${directionColor(sig.signal_type)}`}
                        >
                          {sig.signal_type.replace("_signal", "").toUpperCase()}
                          <br />
                          <span className="opacity-60">{sig.confidence.toFixed(0)}%</span>
                        </span>
                      ) : (
                        <span className="text-muted text-xs">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
