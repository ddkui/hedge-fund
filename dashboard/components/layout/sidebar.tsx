// dashboard/components/layout/sidebar.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Cpu, BarChart2, Activity,
  FlaskConical, Server, MessageSquare, ArrowLeftRight, BrainCircuit, TrendingUp, Brain, Wallet, Wand2
} from "lucide-react";

const NAV = [
  { href: "/overview",   label: "Overview",   icon: LayoutDashboard },
  { href: "/trades",     label: "Trades",     icon: ArrowLeftRight },
  { href: "/analytics",  label: "Analytics",  icon: TrendingUp },
  { href: "/consensus",  label: "Consensus",  icon: Cpu },
  { href: "/terminal",   label: "Terminal",   icon: BarChart2 },
  { href: "/activity",   label: "AI Activity",icon: Activity },
  { href: "/quant",      label: "Quant Lab",  icon: FlaskConical },
  { href: "/kronos",     label: "Kronos AI",  icon: BrainCircuit },
  { href: "/intelligence", label: "Intelligence", icon: Brain },
  { href: "/brokers",    label: "Brokers",    icon: Wallet },
  { href: "/hermes",     label: "Hermes",     icon: Wand2 },
  { href: "/ops",        label: "Operations", icon: Server },
  { href: "/chat",       label: "CIO Chat",   icon: MessageSquare },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 min-h-screen bg-surface border-r border-border flex flex-col">
      <div className="px-4 py-5 border-b border-border">
        <span className="text-accent font-bold text-lg tracking-tight">⬡ HedgeFund</span>
        <p className="text-muted text-xs mt-0.5">AI Trading System</p>
      </div>
      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === href
                ? "bg-accent/10 text-accent font-medium"
                : "text-muted hover:text-white hover:bg-white/5"
            }`}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
