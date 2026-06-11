"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

export function InstructionsPanel({
  instructions,
  onChanged,
}: {
  instructions: string[];
  onChanged: (updated: string[]) => void;
}) {
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (!text.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const updated = await apiFetch<string[]>("/hermes/instructions", {
        method: "POST",
        body: JSON.stringify({ text: text.trim() }),
      });
      onChanged(updated);
      setText("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setAdding(false);
    }
  }

  async function remove(idx: number) {
    setRemoving(idx);
    setError(null);
    try {
      const updated = await apiFetch<string[]>(`/hermes/instructions/${idx}`, { method: "DELETE" });
      onChanged(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to remove");
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        CIO Instructions for Hermes Coder
      </h2>
      <p className="text-muted text-xs mb-4">
        These instructions are injected into every code-improvement prompt Hermes generates.
      </p>
      {error && <p className="text-danger text-xs mb-3">{error}</p>}
      <div className="space-y-2 mb-4">
        {instructions.length === 0 ? (
          <p className="text-muted text-sm">No instructions yet.</p>
        ) : (
          instructions.map((inst, i) => (
            <div key={i} className="flex items-start gap-3 bg-white/5 rounded-lg px-4 py-2.5">
              <span className="text-accent font-mono text-xs mt-0.5">{i + 1}</span>
              <span className="text-sm flex-1">{inst}</span>
              <button
                onClick={() => remove(i)}
                disabled={removing === i}
                className="text-muted hover:text-danger text-xs shrink-0 disabled:opacity-50"
                title="Remove"
              >
                {removing === i ? "…" : "✕"}
              </button>
            </div>
          ))
        )}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Add an instruction for Hermes coder…"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") add(); }}
          className="flex-1 bg-transparent border border-border rounded px-3 py-1.5 text-sm focus:border-accent focus:outline-none placeholder:text-muted/50"
        />
        <button
          onClick={add}
          disabled={adding || !text.trim()}
          className="text-sm px-4 py-1.5 rounded bg-accent text-black font-semibold hover:bg-accent/80 disabled:opacity-50"
        >
          {adding ? "…" : "Add"}
        </button>
      </div>
    </div>
  );
}
