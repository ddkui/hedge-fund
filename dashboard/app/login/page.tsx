// dashboard/app/login/page.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [googleClientId, setGoogleClientId] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Fetch Google client ID
    fetch("/api/auth/config")
      .then((r) => r.json())
      .then((d) => setGoogleClientId(d.google_client_id))
      .catch(() => setError("Failed to load sign-in config"));
  }, []);

  useEffect(() => {
    if (!googleClientId || !containerRef.current) return;

    // Dynamically load Google Sign-in script
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleSignInSuccess,
        });
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: "dark",
          size: "large",
          width: "100%",
          text: "signin_with",
        });
      }
    };
    document.body.appendChild(script);
    return () => {
      document.body.removeChild(script);
    };
  }, [googleClientId]);

  async function handleSignInSuccess(response: any) {
    try {
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Sign in failed");
        return;
      }
      const { access_token } = await res.json();
      document.cookie = `hf_token=${access_token}; path=/; max-age=604800; SameSite=Strict`;
      router.push("/overview");
    } catch {
      setError("Connection failed");
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-full max-w-sm bg-surface border border-border rounded-2xl p-8 space-y-6">
        <div className="text-center">
          <p className="text-4xl mb-2">⬡</p>
          <h1 className="text-xl font-bold">AI Hedge Fund</h1>
          <p className="text-muted text-sm mt-1">Sign in with your Google account</p>
        </div>

        {error && <p className="text-danger text-sm text-center">{error}</p>}

        <div ref={containerRef} className="flex justify-center" />

        <p className="text-xs text-muted text-center">
          Only authorized emails can access the dashboard.
        </p>
      </div>
    </div>
  );
}

// Extend window to include Google's types
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: any) => void;
          renderButton: (container: HTMLElement, options: any) => void;
        };
      };
    };
  }
}
