"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

const REGIMES = ["expansion", "contraction", "crisis", "pandemic"];

type WeightsMap = Record<string, Record<string, number>>;

export function WeightsPanel({ data, onSaved }: { data: WeightsMap; onSaved: () => void }) {
  const [activeRegime, setActiveRegime] = useState(REGIMES[0]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const weights = data[activeRegime] ?? {};

  function editKey(agent: string) { return `${activeRegime}:${agent}`; }

  async function save(agent: string) {
    const k = editKey(agent);
    const val = parseFloat(edits[k] ?? String(weights[agent]));
    if (isNaN(val)) return;
    setSaving(k);
    setError(null);
    try {
      await apiFetch("/hermes/weights", {
        method: "PUT",
        body: JSON.stringify({ regime: activeRegime, agent, weight: val }),
      });
      setEdits(prev => { const n = { ...prev }; delete n[k]; return n; });
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Aggregator Weights
      </h2>
      <div className="flex gap-1 mb-4">
        {REGIMES.map(r => (
          <button
            key={r}
            onClick={() => { setActiveRegime(r); setEdits({}); setError(null); }}
            className={`px-3 py-1 text-xs rounded-lg capitalize transition-colors ${
              activeRegime === r
                ? "bg-accent text-black font-semibold"
                : "text-muted hover:text-white hover:bg-white/5"
            }`}
          >
            {r}
          </button>
        ))}
      </div>
      {error && <p className="text-danger text-xs mb-3">{error}</p>}
      {Object.keys(weights).length === 0 ? (
        <p className="text-muted text-sm">No weights configured for {activeRegime}.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2 px-2">Agent</th>
              <th className="py-2 px-2 text-center">Weight</th>
              <th className="py-2 px-2">Scale</th>
              <th className="py-2 px-2 w-16"></th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(weights).sort().map(([agent, w]) => {
              const k = editKey(agent);
              const inputVal = edits[k] !== undefined ? edits[k] : w.toFixed(3);
              const dirty = edits[k] !== undefined;
              const barPct = Math.min(100, (w / 2.5) * 100);
              return (
                <tr key={agent} className="border-b border-border/40 hover:bg-white/5">
                  <td className="py-2 px-2 font-medium capitalize">{agent.replace(/_/g, " ")}</td>
                  <td className="py-2 px-2 text-center">
                    <input
                      type="number"
                      min={0.1}
                      max={2.5}
                      step={0.05}
                      value={inputVal}
                      onChange={e => setEdits(prev => ({ ...prev, [k]: e.target.value }))}
                      className="w-20 bg-transparent border border-border rounded px-2 py-0.5 text-xs font-mono text-center focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td className="py-2 px-2">
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden w-28">
                      <div
                        className="h-full bg-accent rounded-full transition-all"
                        style={{ width: `${barPct}%` }}
                      />
                    </div>
                  </td>
                  <td className="py-2 px-2 text-right">
                    {dirty && (
                      <button
                        onClick={() => save(agent)}
                        disabled={saving === k}
                        className="text-xs px-2 py-0.5 rounded bg-accent text-black font-semibold hover:bg-accent/80 disabled:opacity-50"
                      >
                        {saving === k ? "…" : "Save"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
