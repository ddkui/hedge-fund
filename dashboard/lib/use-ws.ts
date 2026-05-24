// dashboard/lib/use-ws.ts
"use client";
import { useEffect, useRef, useState } from "react";

export interface WsMessage {
  channel: string;
  data: Record<string, unknown>;
}

export function useWebSocket() {
  const [messages, setMessages] = useState<WsMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage;
        if (msg.channel) {
          setMessages((prev) => [msg, ...prev].slice(0, 200));
        }
      } catch {
        // ignore ping frames
      }
    };

    return () => ws.close();
  }, []);

  return { messages, connected };
}

export function useChannelMessages(channel: string) {
  const { messages, connected } = useWebSocket();
  return {
    messages: messages.filter((m) => m.channel === channel),
    connected,
  };
}
