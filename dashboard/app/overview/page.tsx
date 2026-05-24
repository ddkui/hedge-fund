// dashboard/app/overview/page.tsx
import { PnlCard } from "@/components/overview/pnl-card";
import { PositionsTable } from "@/components/overview/positions-table";
import { RegimeBadge } from "@/components/overview/regime-badge";
import { TradeQueue } from "@/components/overview/trade-queue";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Overview</h1>
      <div className="grid grid-cols-3 gap-4">
        <PnlCard />
        <RegimeBadge />
        <TradeQueue />
      </div>
      <PositionsTable />
    </div>
  );
}
