// dashboard/components/chat/cio-chat.tsx
"use client";
import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "cio";
  content: string;
  time: Date;
}

const QUICK_ACTIONS = [
  "Give me the daily briefing",
  "What is the current portfolio status?",
  "Run backtest on momentum strategy",
  "Pause all trading",
];

export function CioChat() {
  const [messages, setMessages] = useState<Message[]>([{
    role: "cio",
    content: "Hello. I am your Chief Investment Officer. Ask me anything about the portfolio, market conditions, or give me instructions.",
    time: new Date(),
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim()) return;
    const userMsg: Message = { role: "user", content: text, time: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "cio", content: data.reply, time: new Date() }]);
    } catch {
      setMessages((prev) => [...prev, { role: "cio", content: "Connection error — check gateway.", time: new Date() }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${msg.role === "cio" ? "bg-accent/20 text-accent" : "bg-purple-500/20 text-purple-400"}`}>
              {msg.role === "cio" ? "CIO" : "ME"}
            </div>
            <div className={`max-w-2xl px-4 py-3 rounded-xl text-sm leading-relaxed ${msg.role === "cio" ? "bg-border text-slate-200" : "bg-purple-500/10 text-slate-200 text-right"}`}>
              {msg.content}
              <p className="text-xs text-muted mt-1">{msg.time.toLocaleTimeString()}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center text-xs font-bold">CIO</div>
            <div className="bg-border px-4 py-3 rounded-xl">
              <span className="text-muted text-sm animate-pulse">Thinking…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="px-4 py-2 border-t border-border flex gap-2 overflow-x-auto">
        {QUICK_ACTIONS.map((action) => (
          <button key={action} onClick={() => send(action)}
            className="shrink-0 px-3 py-1.5 rounded-full bg-border text-muted text-xs hover:text-white hover:bg-white/10 transition-colors">
            {action}
          </button>
        ))}
      </div>
      <div className="p-4 border-t border-border flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
          placeholder="Ask the CIO anything…"
          className="flex-1 bg-border border border-border rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-muted focus:outline-none focus:border-accent transition-colors"
        />
        <button onClick={() => send(input)} disabled={loading || !input.trim()}
          className="px-5 py-3 bg-accent text-black text-sm font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors">
          Send
        </button>
      </div>
    </div>
  );
}
