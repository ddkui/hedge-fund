// dashboard/app/login/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) {
        setError("Incorrect password");
        return;
      }
      const { access_token } = await res.json();
      // Store token in cookie (expires in 24h)
      document.cookie = `hf_token=${access_token}; path=/; max-age=86400; SameSite=Strict`;
      router.push("/overview");
    } catch {
      setError("Connection failed — is the gateway running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-full max-w-sm bg-surface border border-border rounded-2xl p-8 space-y-6">
        <div className="text-center">
          <p className="text-4xl mb-2">⬡</p>
          <h1 className="text-xl font-bold">AI Hedge Fund</h1>
          <p className="text-muted text-sm mt-1">Enter dashboard password to continue</p>
        </div>
        <form onSubmit={handleLogin} className="space-y-4">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full bg-border border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-accent transition-colors"
            autoFocus
          />
          {error && <p className="text-danger text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading || !password}
            className="w-full py-3 bg-accent text-black font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors"
          >
            {loading ? "Logging in…" : "Login"}
          </button>
        </form>
      </div>
    </div>
  );
}
