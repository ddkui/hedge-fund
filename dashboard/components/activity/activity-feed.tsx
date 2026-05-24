// dashboard/components/activity/activity-feed.tsx
"use client";
import { useWebSocket, type WsMessage } from "@/lib/use-ws";

function channelLabel(channel: string) {
  return channel.replace("signals.", "").replace("ops.", "").replace("data.", "");
}

function channelColor(channel: string) {
  if (channel.startsWith("signals.aggregator")) return "text-accent";
  if (channel.startsWith("signals.portfolio")) return "text-purple-400";
  if (channel.startsWith("signals.risk") || channel.includes("risk")) return "text-danger";
  if (channel.startsWith("ops")) return "text-yellow-400";
  return "text-slate-400";
}

export function ActivityFeed() {
  const { messages, connected } = useWebSocket();

  return (
    <div className="bg-surface border border-border rounded-xl p-5 h-[600px] overflow-y-auto">
      <div className="flex items-center justify-between mb-3 sticky top-0 bg-surface pb-2">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Live Agent Activity</h2>
        <span className={`text-xs px-2 py-0.5 rounded-full ${connected ? "text-accent bg-accent/10" : "text-danger bg-danger/10"}`}>
          {connected ? "● LIVE" : "● DISCONNECTED"}
        </span>
      </div>
      {messages.length === 0 ? (
        <p className="text-muted text-sm">Waiting for agent messages… start agents first.</p>
      ) : (
        <div className="space-y-2 font-mono text-xs">
          {messages.map((msg: WsMessage, i: number) => (
            <div key={i} className="flex gap-3 items-start border-b border-border/30 pb-1">
              <span className="text-muted shrink-0">
                {new Date().toLocaleTimeString()}
              </span>
              <span className={`shrink-0 w-28 ${channelColor(msg.channel)}`}>
                [{channelLabel(msg.channel)}]
              </span>
              <span className="text-slate-300 break-all">
                {msg.data.symbol ? `${String(msg.data.symbol)}: ` : ""}
                {(msg.data.signal_type as string) ?? (msg.data.status as string) ?? JSON.stringify(msg.data).slice(0, 120)}
                {msg.data.confidence ? ` (${Number(msg.data.confidence).toFixed(0)}%)` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
