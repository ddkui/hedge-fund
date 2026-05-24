// dashboard/app/quant/page.tsx
import { AlgosTable } from "@/components/quant/algos-table";

export default function QuantPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Quant Lab</h1>
      <AlgosTable />
    </div>
  );
}
