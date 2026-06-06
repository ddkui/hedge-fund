// dashboard/components/intelligence/history-log.tsx
"use client";

interface HistoryEntry {
  id: number;
  time: string;
  agent: string;
  regime: string;
  param_name: string;
  old_value: number;
  new_value: number;
  auto_applied: boolean;
}

export function HistoryLog({ entries }: { entries: HistoryEntry[] }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Parameter Change History
      </h2>
      {entries.length === 0 ? (
        <p className="text-muted text-sm">No changes yet.</p>
      ) : (
        <div className="space-y-1 font-mono text-xs">
          {entries.map((e) => (
            <div key={e.id} className="flex gap-3 items-start border-b border-border/30 py-1.5">
              <span className="text-muted shrink-0 w-20">{new Date(e.time).toLocaleDateString()}</span>
              <span className={`shrink-0 w-4 ${e.auto_applied ? "text-accent" : "text-purple-400"}`}>
                {e.auto_applied ? "A" : "M"}
              </span>
              <span className="text-slate-300">
                {e.agent} › {e.regime} › {e.param_name}: {e.old_value} → {e.new_value}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-muted mt-2">A = auto-applied  M = manual approval</p>
    </div>
  );
}
