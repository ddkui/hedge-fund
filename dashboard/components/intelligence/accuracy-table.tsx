// dashboard/components/intelligence/accuracy-table.tsx
"use client";

interface AgentAccuracy {
  agent: string;
  signals: number;
  accuracy: number;
  avg_pnl: number;
}

export function AccuracyTable({ data }: { data: AgentAccuracy[] }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Agent Accuracy (30d)
      </h2>
      {data.length === 0 ? (
        <p className="text-muted text-sm">No signal outcomes recorded yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2">Agent</th>
              <th className="text-right py-2">Signals</th>
              <th className="text-right py-2">Accuracy</th>
              <th className="text-right py-2">Avg P&L</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.agent} className="border-b border-border/40 hover:bg-white/5">
                <td className="py-2 font-medium capitalize">{row.agent.replace(/_/g, " ")}</td>
                <td className="py-2 text-right font-mono text-muted">{row.signals}</td>
                <td className="py-2 text-right font-mono">
                  <span className={Number(row.accuracy) >= 0.5 ? "text-accent" : "text-danger"}>
                    {(Number(row.accuracy) * 100).toFixed(1)}%
                  </span>
                </td>
                <td className={`py-2 text-right font-mono ${Number(row.avg_pnl) >= 0 ? "text-accent" : "text-danger"}`}>
                  ${Number(row.avg_pnl).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
