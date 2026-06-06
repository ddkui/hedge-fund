// dashboard/app/trades/page.tsx
"use client";
import useSWR from "swr";
import { api, type Trade } from "@/lib/api";
import { useState } from "react";

const STATUS_COLOR: Record<string, string> = {
  executed: "bg-accent/10 text-accent",
  pending: "bg-yellow-500/10 text-yellow-400",
  failed: "bg-danger/10 text-danger",
  denied: "bg-red-900/20 text-red-400",
  cancelled: "bg-gray-500/10 text-gray-400",
};

const ACTION_COLOR: Record<string, string> = {
  long: "text-accent",
  short: "text-danger",
  close: "text-slate-300",
};

function fmtTime(t: string) {
  const d = new Date(t);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function fmtUsd(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(n);
}

export default function TradesPage() {
  const { data: trades = [], isLoading, mutate } = useSWR<Trade[]>(
    "trades-history",
    () => api.trades(200),
    { refreshInterval: 10000 }
  );

  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const statuses = ["all", "executed", "pending", "failed", "denied"];

  const filtered = trades.filter((t) => {
    const matchStatus = filter === "all" || t.status === filter;
    const matchSearch =
      !search ||
      t.symbol.toLowerCase().includes(search.toLowerCase()) ||
      (t.pm_reasoning ?? "").toLowerCase().includes(search.toLowerCase());
    return matchStatus && matchSearch;
  });

  const totalExecuted = trades.filter((t) => t.status === "executed").length;
  const totalValue = trades
    .filter((t) => t.status === "executed")
    .reduce((sum, t) => sum + t.quantity * t.price, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Trade History</h1>
        <button
          onClick={() => mutate()}
          className="text-xs text-muted hover:text-white px-3 py-1 rounded bg-border"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-muted uppercase tracking-widest">Total Trades</p>
          <p className="text-2xl font-bold mt-1">{trades.length}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-muted uppercase tracking-widest">Executed</p>
          <p className="text-2xl font-bold mt-1 text-accent">{totalExecuted}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-muted uppercase tracking-widest">Pending</p>
          <p className="text-2xl font-bold mt-1 text-yellow-400">
            {trades.filter((t) => t.status === "pending").length}
          </p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="text-xs text-muted uppercase tracking-widest">Total Volume</p>
          <p className="text-2xl font-bold mt-1">{fmtUsd(totalValue)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {statuses.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded text-xs capitalize transition-colors ${
                filter === s
                  ? "bg-accent text-black font-bold"
                  : "bg-border text-muted hover:text-white"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Search symbol or reason…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto px-3 py-1 rounded bg-border text-sm text-white placeholder-muted border border-border focus:outline-none focus:border-accent"
        />
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="h-40 animate-pulse bg-border m-4 rounded" />
        ) : filtered.length === 0 ? (
          <p className="text-muted text-sm p-6">No trades found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-xs border-b border-border bg-background/50">
                  <th className="text-left px-4 py-3">Time</th>
                  <th className="text-left px-4 py-3">Symbol</th>
                  <th className="text-left px-4 py-3">Action</th>
                  <th className="text-right px-4 py-3">Qty</th>
                  <th className="text-right px-4 py-3">Fill Price</th>
                  <th className="text-right px-4 py-3">Trade Value</th>
                  <th className="text-right px-4 py-3">Confidence</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Mode</th>
                  <th className="text-left px-4 py-3 max-w-xs">Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-border/40 hover:bg-white/[0.03] transition-colors"
                  >
                    <td className="px-4 py-3 text-muted text-xs font-mono whitespace-nowrap">
                      {fmtTime(t.time)}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold">{t.symbol}</td>
                    <td
                      className={`px-4 py-3 font-medium uppercase text-xs ${
                        ACTION_COLOR[t.action] ?? "text-white"
                      }`}
                    >
                      {t.action}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {t.quantity.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {t.price > 0 ? fmtUsd(t.price) : <span className="text-muted">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-medium">
                      {t.price > 0 ? fmtUsd(t.quantity * t.price) : <span className="text-muted">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {t.confidence > 0 ? (
                        <span
                          className={`text-xs font-mono ${
                            t.confidence >= 70
                              ? "text-accent"
                              : t.confidence >= 50
                              ? "text-yellow-400"
                              : "text-muted"
                          }`}
                        >
                          {t.confidence.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          STATUS_COLOR[t.status] ?? "bg-border text-muted"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          t.paper ? "bg-yellow-500/10 text-yellow-400" : "bg-accent/10 text-accent"
                        }`}
                      >
                        {t.paper ? "PAPER" : "LIVE"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted text-xs max-w-xs">
                      <div className="truncate max-w-[260px]" title={t.pm_reasoning ?? ""}>
                        {t.pm_reasoning ?? "—"}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
