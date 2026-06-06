// dashboard/lib/api.ts
const BASE = "/api";

function getToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/hf_token=([^;]+)/);
  return match ? match[1] : "";
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  portfolio: () => apiFetch<Portfolio>("/portfolio"),
  positions: () => apiFetch<Position[]>("/portfolio/positions"),
  trades: (limit = 100) => apiFetch<Trade[]>(`/portfolio/trades?limit=${limit}`),
  pendingTrades: () => apiFetch<Trade[]>("/trades/pending"),
  approveTrade: (id: number) => apiFetch<{ id: number; status: string }>(`/trades/${id}/approve`, { method: "POST" }),
  denyTrade: (id: number) => apiFetch<{ id: number; status: string }>(`/trades/${id}/deny`, { method: "POST" }),
  signals: (limit = 100) => apiFetch<Signal[]>(`/signals?limit=${limit}`),
  signalsForSymbol: (symbol: string) => apiFetch<Signal[]>(`/signals/${symbol}`),
  agentHealth: () => apiFetch<AgentHealth[]>("/agents/health"),
  algos: () => apiFetch<Algo[]>("/backtests/algos"),
  chat: (message: string) => apiFetch<{ reply: string }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  }),
  prices: (symbol: string, period: string, interval: string) =>
    apiFetch<Candle[]>(`/prices/${symbol}?period=${period}&interval=${interval}`),
  tradeMarkers: (symbol: string) =>
    apiFetch<Trade[]>(`/portfolio/trades?limit=500`),
};

export interface Portfolio {
  cash: number;
  total_value: number;
  peak_value: number;
  open_positions: number;
  time: string | null;
}

export interface Position {
  id: number;
  symbol: string;
  asset_class: string;
  direction: string;
  quantity: number;
  entry_price: number;
  entry_time: string;
  entry_thesis: string | null;
  status: string;
  exit_price: number | null;
  exit_time: string | null;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface Trade {
  id: number;
  symbol: string;
  action: string;
  quantity: number;
  price: number;
  paper: boolean;
  status: string;
  confidence: number;
  pm_reasoning: string | null;
  time: string;
  position_id: number | null;
}

export interface Signal {
  agent: string;
  symbol: string | null;
  signal_type: string;
  confidence: number;
  reasoning: string | null;
  time: string;
}

export interface AgentHealth {
  agent: string;
  status: string;
  time: string;
}

export interface Algo {
  id: number;
  name: string;
  quant_agent: string;
  strategy_type: string;
  status: string;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  trade_count: number | null;
  created_at: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
