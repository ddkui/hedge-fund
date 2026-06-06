// dashboard/components/intelligence/proposals-list.tsx
"use client";
import { apiFetch } from "@/lib/api";

interface Proposal {
  id: number;
  agent: string;
  regime: string;
  param_name: string;
  current_value: number;
  proposed_value: number;
  change_pct: number;
  reason: string;
}

interface ProposalsListProps {
  proposals: Proposal[];
  onReview: () => void;
}

export function ProposalsList({ proposals, onReview }: ProposalsListProps) {
  async function approve(id: number) {
    await apiFetch(`/intelligence/proposals/${id}/approve`, { method: "POST" });
    onReview();
  }
  async function reject(id: number) {
    await apiFetch(`/intelligence/proposals/${id}/reject`, { method: "POST" });
    onReview();
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Pending CIO Proposals
        {proposals.length > 0 && (
          <span className="ml-2 bg-warning/20 text-warning text-xs px-2 py-0.5 rounded-full">
            {proposals.length}
          </span>
        )}
      </h2>
      {proposals.length === 0 ? (
        <p className="text-muted text-sm">No pending proposals.</p>
      ) : (
        <div className="space-y-3">
          {proposals.map((p) => (
            <div key={p.id} className="border border-border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  <span className="font-medium">{p.agent}</span>
                  <span className="text-muted mx-2">›</span>
                  <span className="text-muted">{p.regime}</span>
                  <span className="text-muted mx-2">›</span>
                  <span className="font-mono">{p.param_name}</span>
                </div>
                <span className={`text-xs font-mono ${p.change_pct > 0 ? "text-accent" : "text-danger"}`}>
                  {p.change_pct > 0 ? "+" : ""}{Number(p.change_pct).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm font-mono">
                <span className="text-muted">{p.current_value}</span>
                <span className="text-muted">→</span>
                <span className="text-accent">{p.proposed_value}</span>
              </div>
              <p className="text-xs text-muted">{p.reason}</p>
              <div className="flex gap-2 pt-1">
                <button onClick={() => approve(p.id)}
                  className="flex-1 py-1.5 rounded bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors">
                  ✓ Approve
                </button>
                <button onClick={() => reject(p.id)}
                  className="flex-1 py-1.5 rounded bg-danger/10 text-danger text-xs font-medium hover:bg-danger/20 transition-colors">
                  ✗ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
