// dashboard/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { KillSwitch } from "@/components/layout/kill-switch";

export const metadata: Metadata = {
  title: "AI Hedge Fund",
  description: "Bloomberg-style AI trading dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen bg-background text-slate-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <header className="h-12 border-b border-border bg-surface flex items-center justify-between px-6">
            <span className="text-sm text-muted">Paper Trading Mode</span>
            <KillSwitch />
          </header>
          <main className="flex-1 p-6 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
