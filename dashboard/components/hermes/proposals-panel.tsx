"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { WeightProposal } from "@/lib/api";

export function ProposalsPanel({
  proposals,
  onActioned,
}: {
  proposals: WeightProposal[];
  onActioned: () => void;
}) {
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: number, action: "approve" | "reject") {
    setBusy(id);
    setError(null);
    try {
      await apiFetch(`/hermes/proposals/${id}/${action}`, { method: "POST" });
      onActioned();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Pending Weight Proposals
      </h2>
      {error && <p className="text-danger text-xs mb-3">{error}</p>}
      {proposals.length === 0 ? (
        <p className="text-muted text-sm">No pending proposals.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted text-xs border-b border-border">
                <th className="text-left py-2 px-2">Agent / Regime</th>
                <th className="py-2 px-2 text-center">Current</th>
                <th className="py-2 px-2 text-center">Proposed</th>
                <th className="py-2 px-2 text-center">Δ%</th>
                <th className="py-2 px-2 text-left">Reason</th>
                <th className="py-2 px-2 w-28"></th>
              </tr>
            </thead>
            <tbody>
              {proposals.map(p => {
                const up = p.proposed_value > p.current_value;
                return (
                  <tr key={p.id} className="border-b border-border/40 hover:bg-white/5">
                    <td className="py-2 px-2">
                      <span className="font-medium capitalize">{p.agent.replace(/_/g, " ")}</span>
                      <span className="text-muted text-xs ml-2 capitalize">{p.regime}</span>
                    </td>
                    <td className="py-2 px-2 text-center font-mono text-xs">{Number(p.current_value).toFixed(3)}</td>
                    <td className="py-2 px-2 text-center font-mono text-xs">{Number(p.proposed_value).toFixed(3)}</td>
                    <td className={`py-2 px-2 text-center font-mono text-xs ${up ? "text-accent" : "text-danger"}`}>
                      {up ? "+" : ""}{Number(p.change_pct).toFixed(1)}%
                    </td>
                    <td className="py-2 px-2 text-muted text-xs truncate max-w-[160px]">{p.reason}</td>
                    <td className="py-2 px-2 text-right space-x-1">
                      <button
                        onClick={() => act(p.id, "approve")}
                        disabled={busy === p.id}
                        className="text-xs px-2 py-0.5 rounded bg-accent text-black font-semibold hover:bg-accent/80 disabled:opacity-50"
                      >
                        {busy === p.id ? "…" : "Approve"}
                      </button>
                      <button
                        onClick={() => act(p.id, "reject")}
                        disabled={busy === p.id}
                        className="text-xs px-2 py-0.5 rounded border border-border text-muted hover:text-white disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
