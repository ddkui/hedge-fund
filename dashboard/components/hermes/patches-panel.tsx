"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { CodePatch, CodePatchDetail } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "text-warning border-warning/40",
    applied: "text-accent border-accent/40",
    rejected: "text-danger border-danger/40",
  };
  return (
    <span className={`text-xs border rounded px-1.5 py-0.5 capitalize ${colors[status] ?? "text-muted border-border"}`}>
      {status}
    </span>
  );
}

function DiffView({ original, patched }: { original: string; patched: string }) {
  const origLines = original.split("\n");
  const patchLines = patched.split("\n");
  const origSet = new Set(origLines);
  const patchSet = new Set(patchLines);
  const maxLen = Math.max(origLines.length, patchLines.length);
  const diffs: Array<{ line: string; type: "same" | "removed" | "added" }> = [];

  for (let i = 0; i < maxLen; i++) {
    const o = origLines[i];
    const p = patchLines[i];
    if (o === p) { diffs.push({ line: p ?? "", type: "same" }); continue; }
    if (o !== undefined && !patchSet.has(o)) diffs.push({ line: o, type: "removed" });
    if (p !== undefined && !origSet.has(p)) diffs.push({ line: p, type: "added" });
  }

  return (
    <pre className="text-xs font-mono overflow-auto max-h-64 bg-black/30 rounded p-3 mt-2">
      {diffs.map((d, i) => (
        <div
          key={i}
          className={
            d.type === "removed" ? "text-danger/80 bg-danger/10" :
            d.type === "added" ? "text-accent/80 bg-accent/10" :
            "text-muted/60"
          }
        >
          {d.type === "removed" ? "- " : d.type === "added" ? "+ " : "  "}{d.line}
        </div>
      ))}
    </pre>
  );
}

export function PatchesPanel({
  patches,
  onActioned,
}: {
  patches: CodePatch[];
  onActioned: () => void;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<CodePatchDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function expand(id: number) {
    if (expanded === id) { setExpanded(null); setDetail(null); return; }
    setExpanded(id);
    setLoadingDetail(true);
    try {
      const d = await apiFetch<CodePatchDetail>(`/hermes/patches/${id}`);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }

  async function act(id: number, action: "apply" | "reject") {
    setBusy(id);
    setError(null);
    try {
      await apiFetch(`/hermes/patches/${id}/${action}`, { method: "POST" });
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
        AI Code Patches
      </h2>
      {error && <p className="text-danger text-xs mb-3">{error}</p>}
      {patches.length === 0 ? (
        <p className="text-muted text-sm">No patches generated yet.</p>
      ) : (
        <div className="space-y-2">
          {patches.map(p => (
            <div key={p.id} className="border border-border/60 rounded-lg overflow-hidden">
              <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/5"
                onClick={() => expand(p.id)}
              >
                <StatusBadge status={p.status} />
                <span className="font-medium capitalize text-sm">{p.agent_name.replace(/_/g, " ")}</span>
                <span className="text-muted text-xs capitalize">{p.regime}</span>
                <span className="text-muted text-xs font-mono">wr={(((p.win_rate ?? 0) * 100).toFixed(0))}%</span>
                <span className="text-muted text-xs truncate flex-1">{p.description}</span>
                <span className="text-muted text-xs">{expanded === p.id ? "▲" : "▼"}</span>
              </div>
              {expanded === p.id && (
                <div className="border-t border-border/40 px-4 py-3">
                  <p className="text-muted text-xs mb-1">
                    <span className="text-white/60">File:</span> {p.file_path}
                    <span className="ml-4 text-white/60">Reason:</span> {p.reason}
                  </p>
                  {loadingDetail ? (
                    <p className="text-muted text-xs">Loading diff…</p>
                  ) : detail?.id === p.id ? (
                    <DiffView original={detail.original_content} patched={detail.patched_content} />
                  ) : null}
                  {p.status === "pending" && (
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => act(p.id, "apply")}
                        disabled={busy === p.id}
                        className="text-xs px-3 py-1 rounded bg-accent text-black font-semibold hover:bg-accent/80 disabled:opacity-50"
                      >
                        {busy === p.id ? "…" : "Apply to Disk"}
                      </button>
                      <button
                        onClick={() => act(p.id, "reject")}
                        disabled={busy === p.id}
                        className="text-xs px-3 py-1 rounded border border-border text-muted hover:text-white disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
