"use client";
import useSWR from "swr";
import { useState } from "react";
import { apiFetch, api } from "@/lib/api";
import type { WinRateRow, WeightProposal, CodePatch } from "@/lib/api";
import { WinRateGrid } from "@/components/hermes/win-rate-grid";
import { WeightsPanel } from "@/components/hermes/weights-panel";
import { ProposalsPanel } from "@/components/hermes/proposals-panel";
import { PatchesPanel } from "@/components/hermes/patches-panel";
import { InstructionsPanel } from "@/components/hermes/instructions-panel";

type TriggerResult = { agent_regimes_analyzed: number; auto_applied: number; queued_for_approval: number };

export default function HermesPage() {
  const { data: winRates = [], mutate: mutateWinRates } = useSWR<WinRateRow[]>(
    "hermes-win-rates", api.hermes.winRates, { refreshInterval: 60000 }
  );
  const { data: weights = {}, mutate: mutateWeights } = useSWR(
    "hermes-weights", api.hermes.weights, { refreshInterval: 30000 }
  );
  const { data: proposals = [], mutate: mutateProposals } = useSWR<WeightProposal[]>(
    "hermes-proposals", api.hermes.proposals, { refreshInterval: 30000 }
  );
  const { data: patches = [], mutate: mutatePatches } = useSWR<CodePatch[]>(
    "hermes-patches", api.hermes.patches, { refreshInterval: 30000 }
  );
  const { data: instructions = [], mutate: mutateInstructions } = useSWR<string[]>(
    "hermes-instructions", api.hermes.instructions
  );

  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<TriggerResult | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  async function runTrigger() {
    setTriggering(true);
    setTriggerResult(null);
    setTriggerError(null);
    try {
      const res = await apiFetch<TriggerResult>("/hermes/trigger", { method: "POST" });
      setTriggerResult(res);
      mutateWinRates();
      mutateWeights();
      mutateProposals();
    } catch (e: unknown) {
      setTriggerError(e instanceof Error ? e.message : "Trigger failed");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Hermes</h1>
          <p className="text-muted text-xs mt-0.5">Self-improving meta-agent — weights, patches, and CIO instructions</p>
        </div>
        <div className="flex items-center gap-3">
          {triggerResult && (
            <span className="text-xs text-muted">
              Analyzed <span className="text-white">{triggerResult.agent_regimes_analyzed}</span> groups ·{" "}
              <span className="text-accent">{triggerResult.auto_applied} applied</span> ·{" "}
              <span className="text-warning">{triggerResult.queued_for_approval} queued</span>
            </span>
          )}
          {triggerError && <span className="text-danger text-xs">{triggerError}</span>}
          <button
            onClick={runTrigger}
            disabled={triggering}
            className="text-sm px-4 py-1.5 rounded bg-accent text-black font-semibold hover:bg-accent/80 disabled:opacity-50"
          >
            {triggering ? "Running…" : "Run Cycle Now"}
          </button>
        </div>
      </div>

      <WinRateGrid data={winRates} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WeightsPanel data={weights} onSaved={() => mutateWeights()} />
        <ProposalsPanel proposals={proposals} onActioned={() => mutateProposals()} />
      </div>

      <PatchesPanel patches={patches} onActioned={() => mutatePatches()} />

      <InstructionsPanel
        instructions={instructions}
        onChanged={updated => mutateInstructions(updated, false)}
      />
    </div>
  );
}
