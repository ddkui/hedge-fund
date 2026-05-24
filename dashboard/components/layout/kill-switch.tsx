// dashboard/components/layout/kill-switch.tsx
"use client";
import { useState, useEffect } from "react";

export function KillSwitch() {
  const [active, setActive] = useState(false);

  useEffect(() => {
    fetch("/api/chat/kill-switch/status")
      .then(r => r.json())
      .then(d => setActive(d.halted))
      .catch(() => {});
  }, []);

  async function toggle() {
    const endpoint = active ? "/api/chat/kill-switch/resume" : "/api/chat/kill-switch/halt";
    try {
      const res = await fetch(endpoint, { method: "POST" });
      if (res.ok) setActive(!active);
    } catch {
      alert("Failed to reach gateway");
    }
  }

  return (
    <button
      onClick={toggle}
      className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wide border transition-all ${
        active
          ? "bg-danger border-danger text-white animate-pulse"
          : "bg-transparent border-danger text-danger hover:bg-danger hover:text-white"
      }`}
    >
      {active ? "● TRADING HALTED" : "KILL SWITCH"}
    </button>
  );
}
