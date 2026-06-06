// dashboard/app/login/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [step, setStep] = useState<"email" | "otp">("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const router = useRouter();

  async function requestOtp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/request-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Failed to send code");
        return;
      }
      setStep("otp");
      startResendCooldown();
    } catch {
      setError("Connection failed — is the gateway running?");
    } finally {
      setLoading(false);
    }
  }

  function startResendCooldown() {
    setResendCooldown(60);
    const interval = setInterval(() => {
      setResendCooldown((c) => {
        if (c <= 1) { clearInterval(interval); return 0; }
        return c - 1;
      });
    }, 1000);
  }

  async function verifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, otp }),
      });
      if (!res.ok) {
        setError("Invalid or expired code. Try again.");
        return;
      }
      const { access_token } = await res.json();
      document.cookie = `hf_token=${access_token}; path=/; max-age=86400; SameSite=Strict`;
      router.push("/overview");
    } catch {
      setError("Connection failed");
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
          <p className="text-muted text-sm mt-1">
            {step === "email" ? "Enter your email to receive a login code" : `Code sent to ${email}`}
          </p>
        </div>

        {step === "email" ? (
          <form onSubmit={requestOtp} className="space-y-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              className="w-full bg-border border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-accent transition-colors"
              autoFocus
              required
            />
            {error && <p className="text-danger text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3 bg-accent text-black font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors"
            >
              {loading ? "Sending…" : "Send Login Code"}
            </button>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="space-y-4">
            <input
              type="text"
              value={otp}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                setOtp(v);
              }}
              placeholder="000000"
              className="w-full bg-border border border-border rounded-xl px-4 py-3 text-sm text-center text-2xl tracking-[0.5em] font-mono focus:outline-none focus:border-accent transition-colors"
              autoFocus
              maxLength={6}
              required
            />
            {error && <p className="text-danger text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading || otp.length !== 6}
              className="w-full py-3 bg-accent text-black font-bold rounded-xl hover:bg-accent/80 disabled:opacity-40 transition-colors"
            >
              {loading ? "Verifying…" : "Verify Code"}
            </button>
            <div className="text-center">
              <button
                type="button"
                onClick={requestOtp}
                disabled={resendCooldown > 0}
                className="text-muted text-sm hover:text-white disabled:opacity-40 transition-colors"
              >
                {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : "Resend code"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
