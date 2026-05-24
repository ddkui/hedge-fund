// dashboard/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { ShellWrapper } from "@/components/layout/shell-wrapper";

export const metadata: Metadata = {
  title: "AI Hedge Fund",
  description: "Bloomberg-style AI trading dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen bg-background text-slate-200">
        <ShellWrapper>{children}</ShellWrapper>
      </body>
    </html>
  );
}
