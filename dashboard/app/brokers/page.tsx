// dashboard/app/brokers/page.tsx
"use client";
import useSWR from "swr";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

interface BrokerAccount {
  name: string;
  type: string;
  enabled: boolean;
  api_key?: string;
  secret_key?: string;
  paper?: boolean;
  host?: string;
  port?: number;
  client_id?: number;
  identifier?: string;
  base_url?: string;
}

const BROKER_TYPES = [
  { value: "alpaca", label: "Alpaca" },
  { value: "ib", label: "Interactive Brokers" },
  { value: "capital_com", label: "Capital.com" },
];

const EMPTY_FORM = {
  name: "", type: "alpaca", enabled: true,
  api_key: "", secret_key: "", paper: true,
  host: "127.0.0.1", port: 7497, client_id: 1,
  identifier: "", password: "", base_url: "",
};

export default function BrokersPage() {
  const { data: accounts = [], mutate } = useSWR<BrokerAccount[]>(
    "broker-accounts", () => apiFetch("/brokers/accounts"), { refreshInterval: 30000 }
  );
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);

  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function addAccount(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    // Only send fields relevant to the broker type
    const base: any = { name: form.name, type: form.type, enabled: form.enabled };
    if (form.type === "alpaca") {
      base.api_key = form.api_key; base.secret_key = form.secret_key; base.paper = form.paper;
    } else if (form.type === "ib") {
      base.host = form.host; base.port = Number(form.port); base.client_id = Number(form.client_id);
    } else if (form.type === "capital_com") {
      base.api_key = form.api_key; base.identifier = form.identifier;
      base.password = form.password; base.base_url = form.base_url;
    }
    try {
      const res = await fetch("/api/brokers/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(base),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Failed to add broker");
        return;
      }
      setForm({ ...EMPTY_FORM });
      setShowForm(false);
      mutate();
    } catch {
      setError("Connection failed");
    } finally {
      setSaving(false);
    }
  }

  async function removeAccount(name: string) {
    if (!confirm(`Remove broker "${name}"? This stops copying trades to it.`)) return;
    await fetch(`/api/brokers/accounts/${name}`, { method: "DELETE" });
    mutate();
  }

  async function toggleAccount(name: string, enabled: boolean) {
    await fetch(`/api/brokers/accounts/${name}/toggle`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    mutate();
  }

  const inputCls = "w-full bg-border border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent transition-colors";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Broker Accounts</h1>
          <p className="text-sm text-muted mt-0.5">
            Every enabled account receives a copy of each trade simultaneously
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="px-4 py-2 bg-accent text-black text-sm font-bold rounded-lg hover:bg-accent/80 transition-colors"
        >
          {showForm ? "Cancel" : "+ Add Broker"}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form onSubmit={addAccount} className="bg-surface border border-border rounded-xl p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted uppercase tracking-widest">Account Name</label>
              <input className={inputCls} placeholder="investor-john"
                value={form.name} onChange={(e) => set("name", e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-muted uppercase tracking-widest">Broker</label>
              <select className={inputCls} value={form.type} onChange={(e) => set("type", e.target.value)}>
                {BROKER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>

          {form.type === "alpaca" && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">API Key</label>
                <input className={inputCls} value={form.api_key} onChange={(e) => set("api_key", e.target.value)} required />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Secret Key</label>
                <input type="password" className={inputCls} value={form.secret_key} onChange={(e) => set("secret_key", e.target.value)} required />
              </div>
              <label className="flex items-center gap-2 text-sm col-span-2">
                <input type="checkbox" checked={form.paper} onChange={(e) => set("paper", e.target.checked)} />
                Paper trading (uncheck for live money)
              </label>
            </div>
          )}

          {form.type === "ib" && (
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Host</label>
                <input className={inputCls} value={form.host} onChange={(e) => set("host", e.target.value)} />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Port (7497 paper / 7496 live)</label>
                <input type="number" className={inputCls} value={form.port} onChange={(e) => set("port", Number(e.target.value))} />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Client ID (unique)</label>
                <input type="number" className={inputCls} value={form.client_id} onChange={(e) => set("client_id", Number(e.target.value))} />
              </div>
            </div>
          )}

          {form.type === "capital_com" && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">API Key</label>
                <input className={inputCls} value={form.api_key} onChange={(e) => set("api_key", e.target.value)} required />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Identifier (email)</label>
                <input className={inputCls} value={form.identifier} onChange={(e) => set("identifier", e.target.value)} required />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Password</label>
                <input type="password" className={inputCls} value={form.password} onChange={(e) => set("password", e.target.value)} required />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-widest">Base URL</label>
                <input className={inputCls} placeholder="https://api-capital.backend.gbksoft.net"
                  value={form.base_url} onChange={(e) => set("base_url", e.target.value)} />
              </div>
            </div>
          )}

          {error && <p className="text-danger text-sm">{error}</p>}
          <button type="submit" disabled={saving}
            className="px-5 py-2.5 bg-accent text-black text-sm font-bold rounded-lg hover:bg-accent/80 disabled:opacity-40 transition-colors">
            {saving ? "Saving…" : "Save Broker Account"}
          </button>
        </form>
      )}

      {/* Account list */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">
            Connected Accounts
          </h2>
          <span className="text-xs text-muted">
            {accounts.filter((a) => a.enabled).length} active / {accounts.length} total
          </span>
        </div>
        {accounts.length === 0 ? (
          <div className="p-8 text-center text-muted text-sm">
            No broker accounts yet. Click "+ Add Broker" to connect one.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted text-xs border-b border-border">
                <th className="text-left px-5 py-3">Name</th>
                <th className="text-left px-3 py-3">Type</th>
                <th className="text-left px-3 py-3">Credentials</th>
                <th className="text-center px-3 py-3">Status</th>
                <th className="text-right px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.name} className="border-b border-border/40 hover:bg-white/5">
                  <td className="px-5 py-3 font-medium">{a.name}</td>
                  <td className="px-3 py-3 text-muted">{a.type}</td>
                  <td className="px-3 py-3 font-mono text-xs text-muted">
                    {a.api_key ? `key ${a.api_key}` : a.host ? `${a.host}:${a.port} (id ${a.client_id})` : "—"}
                    {a.paper !== undefined && (a.paper ? " · paper" : " · LIVE")}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <button onClick={() => toggleAccount(a.name, !a.enabled)}
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        a.enabled ? "bg-accent/10 text-accent" : "bg-muted/10 text-muted"
                      }`}>
                      {a.enabled ? "● ACTIVE" : "○ DISABLED"}
                    </button>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button onClick={() => removeAccount(a.name)}
                      className="text-danger text-xs hover:underline">
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-muted">
        Credentials are stored on your server in <code>brokers.yaml</code> and never shown in full again.
        Changes take effect when the execution agent restarts.
      </p>
    </div>
  );
}
