// dashboard/components/layout/shell-wrapper.tsx
"use client";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { KillSwitch } from "./kill-switch";

export function ShellWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  if (isLoginPage) {
    return <>{children}</>;
  }

  return (
    <>
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
    </>
  );
}
