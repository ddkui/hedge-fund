// dashboard/app/intelligence/page.tsx
"use client";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";
import { AlphaStatus } from "@/components/intelligence/alpha-status";
import { AccuracyTable } from "@/components/intelligence/accuracy-table";
import { ProposalsList } from "@/components/intelligence/proposals-list";
import { HistoryLog } from "@/components/intelligence/history-log";

export default function IntelligencePage() {
  const { data: status } = useSWR("intelligence-status",
    () => apiFetch("/intelligence/status"), { refreshInterval: 30000 });

  const { data: accuracy = [] } = useSWR("intelligence-accuracy",
    () => apiFetch("/intelligence/accuracy"), { refreshInterval: 60000 });

  const { data: proposals = [], mutate: mutateProposals } = useSWR("intelligence-proposals",
    () => apiFetch("/intelligence/proposals"), { refreshInterval: 10000 });

  const { data: history = [] } = useSWR("intelligence-history",
    () => apiFetch("/intelligence/history"), { refreshInterval: 60000 });

  const { data: regimeData } = useSWR("macro-regime",
    () => apiFetch("/signals/MACRO"), { refreshInterval: 60000 });

  const currentRegime = (regimeData as any)?.[0]?.signal_type || "unknown";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Intelligence</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">Regime:</span>
          <span className="px-3 py-1 bg-accent/10 text-accent text-xs font-bold rounded-full uppercase">
            {String(currentRegime).replace(/_/g, " ")}
          </span>
        </div>
      </div>

      <AlphaStatus data={status as any} />

      <div className="grid grid-cols-2 gap-4">
        <AccuracyTable data={accuracy as any[]} />
        <ProposalsList proposals={proposals as any[]} onReview={mutateProposals} />
      </div>

      <HistoryLog entries={history as any[]} />
    </div>
  );
}
