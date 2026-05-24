// dashboard/components/overview/trade-queue.tsx
"use client";
import useSWR from "swr";
import { api, type Trade } from "@/lib/api";

export function TradeQueue() {
  const { data = [], mutate, isLoading } = useSWR<Trade[]>("pending-trades", api.pendingTrades, { refreshInterval: 5000 });

  async function approve(id: number) {
    await api.approveTrade(id);
    mutate();
  }
  async function deny(id: number) {
    await api.denyTrade(id);
    mutate();
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-3 text-muted uppercase tracking-widest">
        Trade Approval Queue
        {data.length > 0 && (
          <span className="ml-2 bg-warning/20 text-warning text-xs px-2 py-0.5 rounded-full">{data.length}</span>
        )}
      </h2>
      {isLoading ? (
        <div className="h-16 animate-pulse bg-border rounded" />
      ) : data.length === 0 ? (
        <p className="text-muted text-sm">No pending trades</p>
      ) : (
        <div className="space-y-3">
          {data.map((t) => (
            <div key={t.id} className="border border-border rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold">{t.symbol}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${t.action === "long" ? "text-accent bg-accent/10" : "text-danger bg-danger/10"}`}>
                    {t.action.toUpperCase()}
                  </span>
                  <span className="text-muted text-xs">{t.quantity.toFixed(4)} @ ${t.price.toFixed(2)}</span>
                </div>
                <span className="text-xs text-warning">{t.confidence.toFixed(0)}% confidence</span>
              </div>
              <p className="text-xs text-muted">{t.pm_reasoning}</p>
              <div className="flex gap-2">
                <button onClick={() => approve(t.id)}
                  className="flex-1 py-1.5 rounded bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors">
                  ✓ Approve
                </button>
                <button onClick={() => deny(t.id)}
                  className="flex-1 py-1.5 rounded bg-danger/10 text-danger text-xs font-medium hover:bg-danger/20 transition-colors">
                  ✗ Deny
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
