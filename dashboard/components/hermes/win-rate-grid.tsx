"use client";

interface WinRateRow {
  agent: string;
  regime: string;
  wins: number;
  total: number;
  win_rate: number;
}

const REGIMES = ["expansion", "contraction", "crisis", "pandemic"];

function WinCell({ wr, total }: { wr?: number; total?: number }) {
  if (!wr || !total || total === 0)
    return <span className="text-muted">—</span>;
  const pct = (wr * 100).toFixed(0);
  const color = wr >= 0.70 ? "text-accent" : wr < 0.45 ? "text-danger" : "text-warning";
  return (
    <span className={`font-mono text-xs ${color}`}>
      {pct}%<span className="text-muted ml-1">({total})</span>
    </span>
  );
}

export function WinRateGrid({ data }: { data: WinRateRow[] }) {
  const idx: Record<string, Record<string, WinRateRow>> = {};
  for (const r of data) {
    if (!idx[r.agent]) idx[r.agent] = {};
    idx[r.agent][r.regime] = r;
  }
  const agents = Object.keys(idx).sort();

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Win Rates — 30 days
        <span className="ml-3 text-xs font-normal normal-case">
          <span className="text-accent">■</span> ≥70%&nbsp;
          <span className="text-warning">■</span> 45–70%&nbsp;
          <span className="text-danger">■</span> &lt;45%
        </span>
      </h2>
      {agents.length === 0 ? (
        <p className="text-muted text-sm">No signal outcomes yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted text-xs border-b border-border">
                <th className="text-left py-2 px-2">Agent</th>
                {REGIMES.map(r => (
                  <th key={r} className="py-2 px-2 text-center capitalize">{r}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {agents.map(agent => (
                <tr key={agent} className="border-b border-border/40 hover:bg-white/5">
                  <td className="py-2 px-2 font-medium capitalize">{agent.replace(/_/g, " ")}</td>
                  {REGIMES.map(regime => (
                    <td key={regime} className="py-2 px-2 text-center">
                      <WinCell wr={idx[agent]?.[regime]?.win_rate} total={idx[agent]?.[regime]?.total} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
